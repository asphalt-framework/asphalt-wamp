from asyncio import wait, wait_for, Future, Lock, get_event_loop, FIRST_EXCEPTION
from inspect import isawaitable
from ssl import SSLContext
from typing import Callable, Iterable, Optional, Union

import txaio
from autobahn.asyncio.wamp import ApplicationSession
from autobahn.asyncio.websocket import WampWebSocketClientFactory
from autobahn.wamp import auth
from autobahn.wamp.types import (
    ComponentConfig, SessionDetails, EventDetails, CallDetails, PublishOptions, CallOptions,
    CloseDetails, Challenge, SubscribeOptions, RegisterOptions)
from autobahn.websocket.util import parse_url
from functools import partial
from typeguard import check_argument_types

from asphalt.core import Context, EventSource, resolve_reference, register_topic
from asphalt.serialization.api import Serializer
from asphalt.serialization.serializers.cbor import CBORSerializer
from asphalt.wamp.context import CallContext, EventContext
from asphalt.wamp.events import SessionJoinEvent, SessionLeaveEvent
from asphalt.wamp.registry import WAMPRegistry, Procedure, Subscriber
from asphalt.wamp.serializers import wrap_serializer

__all__ = ('AuthenticationError', 'WAMPClient')


class AuthenticationError(Exception):
    """Raised when authentication against the WAMP router fails."""

    def __init__(self, reason: str):
        super().__init__(reason)


class AsphaltSession(ApplicationSession):
    def __init__(self, realm: str, auth_method: Optional[str], auth_id: Optional[str],
                 auth_secret: Optional[str], join_future: Future):
        super().__init__(ComponentConfig(realm))
        self.__auth_id = auth_id
        self.__auth_secret = auth_secret
        self.__auth_method = auth_method
        self.__join_future = join_future

    def onConnect(self):
        auth_methods = [self.__auth_method] if self.__auth_method else None
        self.join(self.config.realm, auth_methods, self.__auth_id)

    def onJoin(self, details: SessionDetails):
        self.__join_future.set_result(details)
        self.__join_future = None

    def onLeave(self, details):
        super().onLeave(details)
        if self.__join_future:
            exc = AuthenticationError(details.message)
            self.__join_future.set_exception(exc)
            self.__join_future = None

    def onChallenge(self, challenge: Challenge):
        if challenge.method != self.__auth_method:
            raise Exception('Expected authentication method "{}" but received a "{}" challenge '
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


@register_topic('realm_joined', SessionJoinEvent)
@register_topic('realm_left', SessionLeaveEvent)
class WAMPClient(EventSource):
    """
    A WAMP client.

    Supported events:

    * ``realm_joined`` (:class:`~asphalt.wamp.events.SessionJoinEvent`): the client has joined
      the realm and has registered any procedures and subscribers on its assigned router
    * ``realm_left`` (:class:`~asphalt.wamp.events.SessionLeaveEvent`): the client has left
      the realm

    :param realm: the WAMP realm to join the application session to (defaults to the resource
        name if not specified)
    :param url: the websocket URL to connect to
    :param registry: a WAMP registry or a string reference to one (defaults to creating a new
        instance if omitted)
    :param ssl_context: an SSL context or the name of an :class:`ssl.SSLContext` resource
    :param serializer: a serializer instance or the name of a
        :class:`asphalt.serialization.api.Serializer` resource (defaults to creating a new
        :class:`~asphalt.serialization.cbor.CBORSerializer` if omitted)
    :param auth_method: authentication method to use (valid values are currently ``anonymous``,
        ``wampcra`` and ``ticket``)
    :param auth_id: authentication ID (username)
    :param auth_secret: secret to use for authentication (ticket or password)

    :ivar str realm: the WAMP realm
    :ivar str url: the WAMP URL
    """

    def __init__(self, url: str, realm: str='default', *, registry: Union[WAMPRegistry, str]=None,
                 ssl_context: SSLContext=None, serializer: Union[Serializer, str]=None,
                 auth_method: str='anonymous', auth_id: str=None, auth_secret: str=None):
        check_argument_types()
        super().__init__()
        self.context = None
        self.url = url
        self.realm = realm
        self.registry = resolve_reference(registry) if registry is not None else WAMPRegistry()
        self.ssl_context = ssl_context
        self.serializer = serializer if serializer is not None else CBORSerializer()
        self.auth_method = auth_method
        self.auth_id = auth_id
        self.auth_secret = auth_secret

        self._lock = Lock()
        self._session = None  # type: AsphaltSession
        self._session_details = None  # type: SessionDetails

    async def _register(self, procedure: Procedure):
        async def wrapper(*args, _call_details: CallDetails, **kwargs):
            async with CallContext(self.context, self._session_details, _call_details) as ctx:
                retval = procedure.handler(ctx, *args, **kwargs)
                if isawaitable(retval):
                    retval = await retval

            return retval

        options = RegisterOptions(details_arg='_call_details', **procedure.options)
        return await self._session.register(wrapper, procedure.name, options)

    async def _subscribe(self, subscriber: Subscriber):
        async def wrapper(*args, _event_details: EventDetails, **kwargs):
            async with EventContext(self.context, self._session_details, _event_details) as ctx:
                retval = subscriber.handler(ctx, *args, **kwargs)
                if isawaitable(retval):
                    await retval

        options = SubscribeOptions(details_arg='_event_details', **subscriber.options)
        await self._session.subscribe(wrapper, subscriber.topic, options)

    async def start(self, ctx: Context):
        self.context = ctx
        if isinstance(self.ssl_context, str):
            self.ssl_context = await ctx.request_resource(SSLContext, self.ssl_context)
        if isinstance(self.serializer, str):
            self.serializer = await ctx.request_resource(Serializer, self.serializer)

    async def map_exception(self, exc_class: type, error: str) -> None:
        """
        Map a Python exception to a WAMP error.

        :param exc_class: an exception class
        :param error: the WAMP error code

        """
        self.registry.map_exception(exc_class, error)
        if self._session is None:
            await self.connect()
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
        subscriber = self.registry.add_subscriber(handler, topic, **options)
        if self._session is None:
            await self.connect()  # this will automatically register the subscriber
        else:
            await self._subscribe(subscriber)

    async def publish(self, topic: str, *args, acknowledge: bool=False, exclude_me: bool=None,
                      exclude: Iterable[int]=None, eligible_sessions: Iterable[int]=None,
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

    async def call(self, endpoint: str, *args, on_progress: Callable[..., None]=None,
                   timeout: int=None, **kwargs):
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

    async def connect(self) -> None:
        """
        Connect to the server and join the designated realm if not connected already.

        When joined, registers procedures and event subscriptions on the router from the registry.

        Does nothing if a connection has already been established.

        """
        async def leave_callback(session: AsphaltSession, leave_details: CloseDetails):
            self._session = self._session_details = None
            await self.dispatch_event('realm_left', leave_details)

        async with self._lock:
            if self._session is None:
                is_secure, host, port = parse_url(self.url)[:3]
                ssl = (self.ssl_context or True) if is_secure else False
                join_future = Future()
                session_factory = partial(AsphaltSession, self.realm, self.auth_method,
                                          self.auth_id, self.auth_secret, join_future)
                serializers = [wrap_serializer(self.serializer)]
                loop = txaio.config.loop = get_event_loop()
                transport_factory = WampWebSocketClientFactory(
                    session_factory, url=self.url, serializers=serializers, loop=loop)
                transport, protocol = await loop.create_connection(
                    transport_factory, host, port, ssl=ssl)

                try:
                    # Connection established; wait for the session to join the realm
                    self._session_details = await wait_for(join_future, 10, loop=loop)
                    self._session = protocol._session
                except Exception:
                    transport.close()
                    raise

                try:
                    # Register exception mappings with the session
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
                except Exception:
                    await self._session.leave()
                    self._session = self._session_details = None
                    raise

                self._session.on('leave', leave_callback)

                # Notify listeners that we've joined the realm
                await self.dispatch_event('realm_joined', self._session_details)

    async def disconnect(self) -> None:
        """
        Leave the WAMP realm and disconnect from the server.

        Does nothing if not connected to a server.

        """
        if self._session:
            await self._session.leave()

    @property
    def session_id(self) -> Optional[int]:
        """
        Return the current WAMP session ID.

        :return: the session ID or ``None`` if not in a session.
        """
        return self._session_details.session if self._session_details else None
