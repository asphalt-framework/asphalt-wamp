import logging
from asyncio import wait, wait_for, sleep, Future, get_event_loop, FIRST_EXCEPTION, Task  # noqa
from asyncio.futures import CancelledError
from functools import partial
from inspect import isawaitable
from ssl import SSLContext
from typing import Callable, Iterable, Optional, Union, Awaitable

import txaio
from asphalt.core import Context, resolve_reference, Signal
from asphalt.serialization.api import Serializer
from asphalt.serialization.serializers.cbor import CBORSerializer
from autobahn.asyncio.wamp import ApplicationSession
from autobahn.asyncio.websocket import WampWebSocketClientFactory
from autobahn.wamp import auth
from autobahn.wamp.types import (
    ComponentConfig, SessionDetails, EventDetails, CallDetails, PublishOptions, CallOptions,
    CloseDetails, Challenge, SubscribeOptions, RegisterOptions)
from typeguard import check_argument_types

from asphalt.wamp.context import CallContext, EventContext
from asphalt.wamp.events import SessionJoinEvent, SessionLeaveEvent
from asphalt.wamp.registry import WAMPRegistry, Procedure, Subscriber
from asphalt.wamp.serializers import wrap_serializer

__all__ = ('AuthenticationError', 'WAMPClient')

logger = logging.getLogger(__name__)


class WAMPError(Exception):
    pass


class AuthenticationError(WAMPError):
    """Raised when authentication against the WAMP router fails."""

    def __init__(self, reason: str):
        super().__init__(reason)


class AsphaltSession(ApplicationSession):
    def __init__(self, realm: str, auth_method: str, auth_id: Optional[str],
                 auth_secret: Optional[str], join_future: Future):
        super().__init__(ComponentConfig(realm))
        self.__auth_method = auth_method
        self.__auth_id = auth_id
        self.__auth_secret = auth_secret
        self.__join_future = join_future

    def onConnect(self):
        self.join(self.config.realm, [self.__auth_method], self.__auth_id)

    def onJoin(self, details: SessionDetails):
        if self.__join_future and not self.__join_future.cancelled():
            self.__join_future.set_result((details, self))
            self.__join_future = None

    def onLeave(self, details):
        super().onLeave(details)
        if self.__join_future and not self.__join_future.cancelled():
            exc = AuthenticationError(details.message)
            self.__join_future.set_exception(exc)
            self.__join_future = None

    def onDisconnect(self):
        if self.__join_future and not self.__join_future.cancelled():
            exc = WAMPError('connection closed unexpectedly')
            self.__join_future.set_exception(exc)
            self.__join_future = None

    def onChallenge(self, challenge: Challenge):
        if challenge.method != self.__auth_method:
            raise WAMPError('expected authentication method "{}" but received a "{}" challenge '
                            'instead'.format(self.__auth_method, challenge.method))

        if challenge.method == 'wampcra':
            key = self.__auth_secret
            if 'salt' in challenge.extra:
                # salted secret
                key = auth.derive_key(self.__auth_secret.encode('utf-8'), challenge.extra['salt'],
                                      challenge.extra['iterations'], challenge.extra['keylen'])

            return auth.compute_wcs(key, challenge.extra['challenge'])
        elif challenge.method == 'ticket':
            return self.__auth_secret


class WAMPClient:
    """
    A WAMP client.

    :ivar Signal realm_joined: a signal (:class:`~asphalt.wamp.events.SessionJoinEvent`) dispatched
        when the client has joined the realm and has registered any procedures and subscribers on
        the router
    :ivar Signal realm_left: a signal (:class:`~asphalt.wamp.events.SessionLeaveEvent`) dispatched
        when the client has left the realm
    :ivar str realm: the WAMP realm
    :ivar str url: the WAMP URL
    :ivar WAMPRegistry register: the root registry object
    """

    realm_joined = Signal(SessionJoinEvent)
    realm_left = Signal(SessionLeaveEvent)

    def __init__(self, host: str = 'localhost', port: int = 8080, path: str = '/',
                 realm: str = 'default', *, autoconnect: bool = True, reconnect_delay: int = 5,
                 max_reconnection_attempts: int = None, registry: Union[WAMPRegistry, str] = None,
                 ssl: Union[bool, str, SSLContext] = False,
                 serializer: Union[Serializer, str] = None, auth_method: str = 'anonymous',
                 auth_id: str = None, auth_secret: str = None):
        """
        The following parameters are also available as instance attributes:

        :param host: host address of the WAMP router
        :param port: port to connect to
        :param path: HTTP path on the router
        :param realm: the WAMP realm to join the application session to (defaults to the resource
            name if not specified)
        :param autoconnect: automatically connect when the client is started
        :param reconnect_delay: delay between connection attempts (in seconds)
        :param max_reconnection_attempts: maximum number of connection attempts before giving up
        :param registry: a WAMP registry or a string reference to one (defaults to creating a new
            instance if omitted)
        :param ssl: one of the following:

            * ``False`` to disable SSL
            * ``True`` to enable SSL using the default context
            * an :class:`ssl.SSLContext` instance
            * a ``module:varname`` reference to an :class:`~ssl.SSLContext` instance
            * name of an :class:`ssl.SSLContext` resource
        :param serializer: a serializer instance or the name of a
            :class:`asphalt.serialization.api.Serializer` resource (defaults to creating a new
            :class:`~asphalt.serialization.cbor.CBORSerializer` if omitted)
        :param auth_method: authentication method to use (valid values are currently ``anonymous``,
            ``wampcra`` and ``ticket``)
        :param auth_id: authentication ID (username)
        :param auth_secret: secret to use for authentication (ticket or password)

        """
        assert check_argument_types()
        self.host = host
        self.port = port
        self.path = path
        self.autoconnect = autoconnect
        self.reconnect_delay = reconnect_delay
        self.max_reconnection_attempts = max_reconnection_attempts
        self.realm = realm
        self.registry = resolve_reference(registry) or WAMPRegistry()
        self.ssl = resolve_reference(ssl)
        self.serializer = resolve_reference(serializer) or CBORSerializer({'value_sharing': False})
        self.auth_method = auth_method
        self.auth_id = auth_id
        self.auth_secret = auth_secret

        self._context = None
        self._session = None  # type: AsphaltSession
        self._session_details = None  # type: SessionDetails
        self._connect_task = None  # type: Task

    async def _register(self, procedure: Procedure):
        async def wrapper(*args, _call_details: CallDetails, **kwargs):
            async with CallContext(self._context, self._session_details, _call_details) as ctx:
                retval = procedure.handler(ctx, *args, **kwargs)
                if isawaitable(retval):
                    retval = await retval

            return retval

        options = RegisterOptions(details_arg='_call_details', **procedure.options)
        return await self._session.register(wrapper, procedure.name, options)

    async def _subscribe(self, subscriber: Subscriber):
        async def wrapper(*args, _event_details: EventDetails, **kwargs):
            async with EventContext(self._context, self._session_details, _event_details) as ctx:
                retval = subscriber.handler(ctx, *args, **kwargs)
                if isawaitable(retval):
                    await retval

        options = SubscribeOptions(details_arg='_event_details', **subscriber.options)
        await self._session.subscribe(wrapper, subscriber.topic, options)

    async def start(self, ctx: Context):
        self._context = ctx
        if isinstance(self.ssl, str):
            self.ssl = await ctx.request_resource(SSLContext, self.ssl)
        if isinstance(self.registry, str):
            self.registry = await ctx.request_resource(WAMPRegistry, self.registry)
        if isinstance(self.serializer, str):
            self.serializer = await ctx.request_resource(Serializer, self.serializer)

        if self.autoconnect:
            self.connect()

    async def map_exception(self, exc_class: type, error: str) -> None:
        """
        Map a Python exception to a WAMP error.

        :param exc_class: an exception class
        :param error: the WAMP error code

        """
        self.registry.map_exception(exc_class, error)
        if self._session is None:
            await self.connect()  # this will automatically map the exception
        else:
            self._session.define(exc_class, error)

    async def register_procedure(self, handler: Callable, name: str, **options) -> None:
        """
        Add a procedure handler to the registry and attempts to register it on the router.

        :param handler: callable that handles calls for the given endpoint
        :param name: name of the endpoint to register (e.g. ``x.y.z``)
        :param options: extra keyword arguments to pass to
            :meth:`~.registry.WAMPRegistry.add_procedure`

        """
        assert check_argument_types()
        procedure = self.registry.add_procedure(handler, name, **options)
        if self._session is None:
            await self.connect()  # this will automatically register the procedure
        else:
            await self._register(procedure)

    async def subscribe(self, handler: Callable, topic: str, **options) -> None:
        """
        Add a WAMP event subscriber to the registry and attempts to register it on the router.

        :param handler: the callable that is called when a message arrives
        :param topic: topic to subscribe to
        :param options: extra keyword arguments to pass to
            :meth:`~.registry.WAMPRegistry.add_subscriber`

        """
        assert check_argument_types()
        subscriber = self.registry.add_subscriber(handler, topic, **options)
        if self._session is None:
            await self.connect()  # this will automatically register the subscriber
        else:
            await self._subscribe(subscriber)

    async def publish(self, topic: str, *args, acknowledge: bool = False, exclude_me: bool = None,
                      exclude: Iterable[int] = None, eligible_sessions: Iterable[int] = None,
                      **kwargs) -> Optional[int]:
        """
        Publish an event on the given topic.

        :param topic: the topic to publish on
        :param args: positional arguments to pass to subscribers
        :param acknowledge: ``True`` to wait until the router has acknowledged the event
        :param exclude_me: ``False`` to have the router also send the event back to the sender if
            it has any matching subscriptions
        :param exclude: iterable of WAMP session IDs to exclude from receiving this event
        :param eligible_sessions: list of WAMP session IDs eligible to receive this event
        :param kwargs: keyword arguments to pass to subscribers
        :return: publication ID (with ``acknowledge=True``)

        """
        assert check_argument_types()
        if self._session is None:
            await self.connect()

        kwargs['options'] = PublishOptions(
            acknowledge=acknowledge, exclude_me=exclude_me,
            exclude=list(exclude) if exclude else None,
            eligible=list(eligible_sessions) if eligible_sessions else None)
        retval = self._session.publish(topic, *args, **kwargs)
        if acknowledge:
            publication = await retval
            return publication.id

    async def call(self, endpoint: str, *args, on_progress: Callable[..., None] = None,
                   timeout: int = None, **kwargs):
        """
        Call an RPC function.

        :param endpoint: name of the endpoint to call
        :param args: positional arguments to call the endpoint with
        :param on_progress: a callable that will receive progress reports from the endpoint
        :param timeout: timeout (in seconds) to wait for the completion of the call
        :param kwargs: keyword arguments to call the endpoint with
        :return: the return value of the call
        :raises TimeoutError: if the call times out

        """
        assert check_argument_types()
        if self._session is None:
            await self.connect()

        options = CallOptions(on_progress=on_progress, timeout=timeout)
        return await self._session.call(endpoint, *args, options=options, **kwargs)

    def connect(self) -> Awaitable[None]:
        """
        Connect to the WAMP router and join the designated realm.

        When the realm is successfully joined, exceptions, procedures and event subscriptions from
        the registry are automatically registered with the router.

        The connection process is restarted if connection, joining the realm or registering the
        exceptions/procedures/subscriptions fails. If ``max_connection_attempts`` is set, it will
        limit the number of attempts. If this limit is reached, the awaitable gets the last
        exception set to it. Otherwise, the process is repeated indefinitely until it succeeds.

        If the realm has already been joined, the awaitable completes instantly.

        """
        def _leave_callback(session: AsphaltSession, leave_details: CloseDetails):
            self._session = self._session_details = self._connect_task = None
            self.realm_left.dispatch(leave_details)
            if leave_details.reason == CloseDetails.REASON_TRANSPORT_LOST:
                logger.debug('Connection lost; reconnecting')
                self.connect()

        async def do_connect() -> None:
            proto = 'wss' if self.ssl else 'ws'
            url = '{proto}://{self.host}:{self.port}{self.path}'.format(proto=proto, self=self)
            logger.debug('Connecting to %s:%d (ssl=%s)', self.host, self.port, bool(self.ssl))
            serializers = [wrap_serializer(self.serializer)]
            loop = txaio.config.loop = get_event_loop()
            transport = None
            attempts = 0

            while self._session is None:
                attempts += 1
                try:
                    join_future = Future()
                    session_factory = partial(AsphaltSession, self.realm, self.auth_method,
                                              self.auth_id, self.auth_secret, join_future)
                    transport_factory = WampWebSocketClientFactory(
                        session_factory, url=url, serializers=serializers, loop=loop)
                    transport, protocol = await loop.create_connection(
                        transport_factory, self.host, self.port, ssl=self.ssl)

                    # Connection established; wait for the session to join the realm
                    logger.debug('Connected; attempting to join realm %s', self.realm)
                    self._session_details, self._session = await wait_for(join_future, timeout=5,
                                                                          loop=loop)

                    # Register exception mappings with the session
                    logger.debug(
                        'Realm joined; registering exceptions, subscriptions and procedures')
                    for error, exc_type in self.registry.exceptions.items():
                        self._session.define(exc_type, error)

                    # Register procedures and subscribers with the session
                    tasks = [loop.create_task(self._subscribe(subscriber)) for
                             subscriber in self.registry.subscriptions]
                    tasks += [loop.create_task(self._register(procedure)) for
                              procedure in self.registry.procedures.values()]
                    if tasks:
                        done, not_done = await wait(tasks, loop=loop, timeout=10,
                                                    return_when=FIRST_EXCEPTION)
                        for task in done:
                            if task.exception():
                                raise task.exception()
                except CancelledError:
                    raise
                except Exception as e:
                    if transport:
                        transport.close()

                    self._session = self._session_details = transport = None
                    if (self.max_reconnection_attempts is not None and
                            attempts > self.max_reconnection_attempts):
                        raise

                    logger.info('Connection failed (attempt %d): %s(%s); reconnecting in %d '
                                'seconds', attempts, e.__class__.__name__, e, self.reconnect_delay)
                    await sleep(self.reconnect_delay)

            self._session.on('leave', _leave_callback)

            # Notify listeners that we've joined the realm
            self.realm_joined.dispatch(self._session_details)

            logger.debug('Registration complete')

        # Start a new connection attempt only if not connected and there is no attempt in progress
        if not self._connect_task:
            self._connect_task = get_event_loop().create_task(do_connect())

        return self._connect_task

    async def disconnect(self) -> None:
        """
        Leave the WAMP realm and disconnect from the server.

        If a connection attempt is in progress, it is cancelled.
        Does nothing if not connected to a server.

        """
        if self._session:
            await self._session.leave()
        elif self._connect_task and not self._connect_task.done():
            self._connect_task.cancel()
            self._connect_task = None

    @property
    def session_id(self) -> Optional[int]:
        """
        Return the current WAMP session ID.

        :return: the session ID or ``None`` if not in a session.

        """
        return self._session_details.session if self._session_details else None
