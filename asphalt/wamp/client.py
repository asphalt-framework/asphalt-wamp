import logging
from asyncio import (  # noqa
    wait, wait_for, sleep, Future, Task, shield, AbstractEventLoop, CancelledError, gather)
from functools import partial
from inspect import isawaitable
from ssl import SSLContext
from typing import Callable, Optional, Union, Set, Dict, Any  # noqa

from asphalt.core import Context, resolve_reference, Signal
from asphalt.serialization.api import Serializer
from asphalt.serialization.serializers.json import JSONSerializer
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

__all__ = ('ConnectionError', 'WAMPClient')

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Raised when there was an error connecting to the WAMP router."""


class AsphaltSession(ApplicationSession):
    def __init__(self, client: 'WAMPClient', join_future: Future):
        super().__init__(ComponentConfig(client.realm))
        self.__client = client
        self.__join_future = join_future

    def onConnect(self):
        self.join(self.config.realm, [self.__client.auth_method], self.__client.auth_id)

    def onJoin(self, details: SessionDetails):
        self.__join_future.set_result((details, self))

    def onLeave(self, details):
        super().onLeave(details)
        self.__client._session = None
        self.__client._session_details = None
        self.__client._connect_task = None
        self.__client._subscriptions.clear()
        self.__client._registrations.clear()
        self.__client.realm_left.dispatch(details)
        if details.reason == 'wamp.error.not_authorized':
            if not self.__join_future.done():
                self.__join_future.set_exception(ConnectionError(details.message))
        elif details.reason == CloseDetails.REASON_TRANSPORT_LOST:
            if self.__join_future.done():
                logger.error('Connection lost; reconnecting')
                self.__client.connect()

    def onDisconnect(self):
        if not self.__join_future.done():
            self.__join_future.set_exception(ConnectionError('connection closed unexpectedly'))

    def onChallenge(self, challenge: Challenge):
        if challenge.method != self.__client.auth_method:
            raise ConnectionError(
                'expected authentication method "{}" but received a "{}" challenge instead'.
                format(self.__client.auth_method, challenge.method))

        if challenge.method == 'wampcra':
            key = self.__client.auth_secret
            if 'salt' in challenge.extra:
                # salted secret
                key = auth.derive_key(self.__client.auth_secret.encode('utf-8'),
                                      challenge.extra['salt'], challenge.extra['iterations'],
                                      challenge.extra['keylen'])

            return auth.compute_wcs(key, challenge.extra['challenge'])
        else:  # ticket
            return self.__client.auth_secret


class WAMPClient:
    """
    A WAMP client.

    :ivar Signal realm_joined: a signal (:class:`~asphalt.wamp.events.SessionJoinEvent`) dispatched
        when the client has joined the realm and has registered any procedures and subscribers on
        the router
    :ivar Signal realm_left: a signal (:class:`~asphalt.wamp.events.SessionLeaveEvent`) dispatched
        when the client has left the realm
    """

    realm_joined = Signal(SessionJoinEvent)
    realm_left = Signal(SessionLeaveEvent)

    def __init__(self, host: str = 'localhost', port: int = 8080, path: str = '/ws',
                 realm: str = 'realm1', *, reconnect_delay: Union[int, float] = 5,
                 max_reconnection_attempts: Optional[int] = 15,
                 registry: Union[WAMPRegistry, str] = None, tls: bool = False,
                 tls_context: Union[str, SSLContext] = None,
                 serializer: Union[Serializer, str] = None, auth_method: str = 'anonymous',
                 auth_id: str = None, auth_secret: str = None):
        """
        :param host: host address of the WAMP router
        :param port: port to connect to
        :param path: HTTP path on the router
        :param realm: the WAMP realm to join the application session to (defaults to the resource
            name if not specified)
        :param reconnect_delay: delay between connection attempts (in seconds)
        :param max_reconnection_attempts: maximum number of connection attempts before giving up
        :param registry: a :class:`~asphalt.wamp.registry.WAMPRegistry` instance, a
            ``module:varname`` reference or resource name of one
        :param tls: ``True`` to use TLS when connecting to the router
        :param tls_context: an :class:`~ssl.SSLContext` instance or the resource name of one
        :param serializer: a :class:`asphalt.serialization.api.Serializer` instance or the resource
            name of one
        :param auth_method: authentication method to use (valid values are currently ``anonymous``,
            ``wampcra`` and ``ticket``)
        :param auth_id: authentication ID (username)
        :param auth_secret: secret to use for authentication (ticket or password)

        """
        assert check_argument_types()
        self.host = host
        self.port = port
        self.path = path
        self.reconnect_delay = reconnect_delay
        self.max_reconnection_attempts = max_reconnection_attempts
        self.realm = realm
        self.tls = tls
        self.tls_context = tls_context
        self.serializer = serializer or JSONSerializer()
        self.auth_method = auth_method
        self.auth_id = auth_id
        self.auth_secret = auth_secret

        self._parent_context = None  # type: Context
        self._loop = None  # type: AbstractEventLoop
        self._registry = resolve_reference(registry) or WAMPRegistry()
        self._session = None  # type: AsphaltSession
        self._session_details = None  # type: SessionDetails
        self._connect_task = None  # type: Task
        self._request_tasks = set()  # type: Set[Task]
        self._registrations = []
        self._subscriptions = []

    async def start(self, ctx: Context):
        self._parent_context = ctx
        self._loop = ctx.loop

        if isinstance(self.tls_context, str):
            self.tls_context = await ctx.request_resource(SSLContext, self.tls_context)
        if isinstance(self.serializer, str):
            self.serializer = await ctx.request_resource(Serializer, self.serializer)
        if isinstance(self._registry, str):
            self._registry = await ctx.request_resource(WAMPRegistry, self._registry)

        registry = WAMPRegistry()
        if self._registry:
            registry.add_from(self._registry)

        self._registry = registry

    async def close(self):
        """
        Finish outstanding tasks and then disconnect from the router.

        First, all subscriptions and registrations are undone to prevent more publications or calls
        from coming in. Next, all outstanding tasks are awaited on. Finally, the client leaves the
        realm and disconnects from the router.

        """
        if self._session:
            sub_futures = [sub.unsubscribe() for sub in self._subscriptions if sub.active]
            proc_futures = [reg.unregister() for reg in self._registrations if reg.active]
            if sub_futures or proc_futures:
                logger.info('Unsubscribing %d subscriptions and unregistering %d procedures',
                            len(sub_futures), len(proc_futures))
                await wait(sub_futures + proc_futures)

            if self._request_tasks:
                logger.info('Waiting for %d WAMP subscription/procedure handler tasks to finish',
                            len(self._request_tasks))
                await wait(self._request_tasks)

            await self._session.leave()
        elif self._connect_task and not self._connect_task.done():
            self._connect_task.cancel()
            await gather(self._connect_task, return_exceptions=True)
            self._connect_task = None

    def map_exception(self, exc_class: type, error: str) -> None:
        """
        Map a Python exception to a WAMP error.

        :param exc_class: an exception class
        :param error: the WAMP error code

        """
        self._registry.map_exception(exc_class, error)
        if self._session:
            self._session.define(exc_class, error)

    async def _register(self, procedure: Procedure):
        async def wrapper(*args, _call_details: CallDetails, **kwargs):
            current_task = Task.current_task(loop=self._loop)
            self._request_tasks.add(current_task)
            try:
                async with CallContext(
                        self._parent_context, self._session_details, _call_details) as ctx:
                    retval = procedure.handler(ctx, *args, **kwargs)
                    if isawaitable(retval):
                        retval = await retval

                return retval
            finally:
                self._request_tasks.remove(current_task)

        procedure.options.details_arg = '_call_details'
        registration = await self._session.register(wrapper, procedure.name, procedure.options)
        self._registrations.append(registration)

    async def _subscribe(self, subscriber: Subscriber):
        async def wrapper(*args, details: EventDetails, **kwargs):
            current_task = Task.current_task(loop=self._loop)
            self._request_tasks.add(current_task)
            try:
                async with EventContext(self._parent_context, self._session_details,
                                        details) as ctx:
                    retval = subscriber.handler(ctx, *args, **kwargs)
                    if isawaitable(retval):
                        await retval
            finally:
                self._request_tasks.remove(current_task)

        subscriber.options.details = True
        subscriber.options.details_arg = 'details'
        subscription = await self._session.subscribe(wrapper, subscriber.topic, subscriber.options)
        self._subscriptions.append(subscription)

    async def register(self, handler: Callable, name: str = None,
                       options: Union[RegisterOptions, Dict[str, Any]] = None) -> None:
        """
        Add a procedure handler to the registry and attempt to register it on the router.

        :param handler: callable that handles calls for the given endpoint
        :param name: name of the endpoint to register (e.g. ``x.y.z``); omit to use the internal
            name of the callable
        :param options: either an Autobahn register options object or a dictionary of keyword
            arguments to make one

        .. note:: the ``details_arg`` option is set by WAMPClient itself so do not attempt to set
                  it yourself.

        """
        assert check_argument_types()
        if isinstance(options, dict):
            options = RegisterOptions(**options)
        elif options is None:
            options = RegisterOptions()

        procedure = self._registry.add_procedure(handler, name, options)
        if self._session is None:
            await self.connect()  # this will automatically register the procedure
        else:
            await self._register(procedure)

    async def subscribe(self, handler: Callable, topic: str,
                        options: Union[SubscribeOptions, Dict[str, Any]] = None) -> None:
        """
        Add a WAMP event subscriber to the registry and attempt to register it on the router.

        :param handler: the callable that is called when a message arrives
        :param topic: topic to subscribe to
        :param options: either an Autobahn subscribe options object or a dictionary of keyword
            arguments to make one

        .. note:: the ``details`` option is set by WAMPClient itself so do not attempt to set it
                  yourself.

        """
        assert check_argument_types()
        if isinstance(options, dict):
            options = SubscribeOptions(**options)
        elif options is None:
            options = SubscribeOptions()

        subscriber = self._registry.add_subscriber(handler, topic, options)
        if self._session is None:
            await self.connect()  # this will automatically register the subscriber
        else:
            await self._subscribe(subscriber)

    async def publish(self, topic: str, *args,
                      options: Union[PublishOptions, Dict[str, Any]] = None,
                      **kwargs) -> Optional[int]:
        """
        Publish an event on the given topic.

        :param topic: the topic to publish on
        :param args: positional arguments to pass to subscribers
        :param options: either an Autobahn publish options object or a dictionary of keyword
            arguments to make one
        :param kwargs: keyword arguments to pass to subscribers
        :return: publication ID (if the ``acknowledge`` option is ``True``)

        """
        assert check_argument_types()
        if self._session is None:
            await self.connect()

        if isinstance(options, dict):
            options = PublishOptions(**options)

        retval = self._session.publish(topic, *args, options=options, **kwargs)
        if options and options.acknowledge:
            publication = await retval
            return publication.id

    async def call(self, endpoint: str, *args, options: Union[CallOptions, Dict[str, Any]] = None,
                   **kwargs):
        """
        Call an RPC function.

        :param endpoint: name of the endpoint to call
        :param args: positional arguments to call the endpoint with
        :param options: either an Autobahn call options object or a dictionary of keyword arguments
            to make one
        :param kwargs: keyword arguments to call the endpoint with
        :return: the return value of the call
        :raises TimeoutError: if the call times out

        """
        assert check_argument_types()
        if self._session is None:
            await self.connect()

        if isinstance(options, dict):
            options = CallOptions(**options)

        return await self._session.call(endpoint, *args, options=options, **kwargs)

    def connect(self) -> Future:
        """
        Connect to the WAMP router and join the designated realm.

        When the realm is successfully joined, exceptions, procedures and event subscriptions from
        the registry are automatically registered with the router.

        The connection process is restarted if connection, joining the realm or registering the
        exceptions/procedures/subscriptions fails. If ``max_connection_attempts`` is set, it will
        limit the number of attempts. If this limit is reached, the future gets the last
        exception set to it. Otherwise, the process is repeated indefinitely until it succeeds.

        If the realm has already been joined, the future completes instantly.

        :raises ConnectionError: if there is a protocol level problem connecting to the router

        """
        async def do_connect() -> None:
            proto = 'wss' if self.tls else 'ws'
            url = '{proto}://{self.host}:{self.port}{self.path}'.format(proto=proto, self=self)
            logger.debug('Connecting to %s:%d (tls=%s)', self.host, self.port, self.tls)
            serializers = [wrap_serializer(self.serializer)]
            transport = None
            attempts = 0

            while self._session is None:
                attempts += 1
                try:
                    join_future = self._loop.create_future()
                    session_factory = partial(AsphaltSession, self, join_future)
                    transport_factory = WampWebSocketClientFactory(
                        session_factory, url=url, serializers=serializers, loop=self._loop)
                    transport, protocol = await self._loop.create_connection(
                        transport_factory, self.host, self.port,
                        ssl=self.tls_context or True if self.tls else False)

                    # Connection established; wait for the session to join the realm
                    logger.debug('Connected to %s; attempting to join realm %s', self.host,
                                 self.realm)
                    self._session_details, self._session = await wait_for(join_future, timeout=5)

                    # Register exception mappings with the session
                    logger.debug(
                        'Realm %r joined; registering %d procedure(s), %d subscription(s) and %d '
                        'exception(s)', self._session_details.realm,
                        len(self._registry.procedures), len(self._registry.subscriptions),
                        len(self._registry.exceptions))
                    for error, exc_type in self._registry.exceptions.items():
                        self._session.define(exc_type, error)

                    # Register procedures with the session
                    for procedure in self._registry.procedures.values():
                        await wait_for(self._register(procedure), 10)

                    # Register subscribers with the session
                    for subscriber in self._registry.subscriptions:
                        await wait_for(self._subscribe(subscriber), 10)
                except Exception as e:
                    if self._session:
                        await self._session.leave()
                    elif transport:
                        transport.close()

                    self._session = self._session_details = transport = None

                    if isinstance(e, CancelledError):
                        logger.info('Connection attempt cancelled')
                        raise

                    if (self.max_reconnection_attempts is not None and
                            attempts > self.max_reconnection_attempts):
                        raise

                    logger.warning('Connection failed (attempt %d): %s(%s); reconnecting in %s '
                                   'seconds', attempts, e.__class__.__name__, e,
                                   self.reconnect_delay)
                    await sleep(self.reconnect_delay)

            # Notify listeners that we've joined the realm
            self.realm_joined.dispatch(self._session_details)

            logger.info('Joined realm %r', self.realm)

        # Start a new connection attempt only if not connected and there is no attempt in progress
        if not self._connect_task or self._connect_task.cancelled():
            self._connect_task = self._loop.create_task(do_connect())
            return self._connect_task
        else:
            return self._connect_task if self._connect_task.done() else shield(self._connect_task)

    @property
    def session_id(self) -> Optional[int]:
        """
        Return the current WAMP session ID.

        :return: the session ID or ``None`` if not in a session.

        """
        return self._session_details.session if self._session_details else None

    @property
    def details(self) -> Optional[SessionDetails]:
        """
        Return the session details object provided by Autobahn if the session has been established.

        """
        return self._session_details
