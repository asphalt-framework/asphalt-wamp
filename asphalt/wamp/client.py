from typing import Callable, Iterable, Optional, Dict, Any, Union
from asyncio import wait, wait_for, coroutine, Future, Lock, get_event_loop, FIRST_EXCEPTION
from functools import partial
from ssl import SSLContext

from typeguard import check_argument_types
from autobahn.asyncio.websocket import WampWebSocketClientFactory
from autobahn.asyncio.wamp import ApplicationSession
from autobahn.wamp.types import (
    ComponentConfig, SessionDetails, EventDetails, CallDetails, PublishOptions, CallOptions,
    CloseDetails, Challenge, SubscribeOptions, RegisterOptions)
from autobahn.wamp import auth
from asphalt.core.context import Context
from asphalt.core.event import EventSource
from asphalt.core.concurrency import asynchronous
from asphalt.core.util import resolve_reference
from asphalt.serialization.api import Serializer
from asphalt.serialization.serializers.cbor import CBORSerializer
from asphalt.wamp.registry import Subscriber, Procedure
from asphalt.wamp.serializers import wrap_serializer
import txaio

from .context import EventContext, CallContext
from .events import SessionJoinEvent, SessionLeaveEvent
from .registry import WAMPRegistry

__all__ = ('AuthenticationError', 'WAMPClient')


class AuthenticationError(Exception):
    """Raised when authentication against the WAMP router fails."""

    def __init__(self, reason: str):
        super().__init__(reason)


class AsphaltSession(ApplicationSession):
    def __init__(self, realm: str, auth_method: Optional[str], auth_id: Optional[str],
                 auth_secret: Optional[str], debug: bool, join_future: Future):
        super().__init__(ComponentConfig(realm))
        self.debug_app = debug
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
    :param call_defaults: default values for the ``timeout`` and ``disclose_me`` keyword arguments
        to :meth:`call`
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
    :param debug_app: ``True`` to enable application level debugging
    :param debug_factory: ``True`` to enable debugging of the client socket factory
    :param debug_code_paths: ``True`` to enable debugging of code paths

    :ivar str realm: the WAMP realm
    :ivar str url: the WAMP URL
    """

    def __init__(self, url: str, realm: str='default', *, call_defaults: Dict[str, Any]=None,
                 registry: Union[WAMPRegistry, str]=None, ssl_context: SSLContext=None,
                 serializer: Union[Serializer, str]=None, auth_method: str='anonymous',
                 auth_id: str=None, auth_secret: str=None, debug_app: bool=False,
                 debug_factory: bool=False, debug_code_paths: bool=False):
        check_argument_types()
        super().__init__()
        self.context = None
        self.url = url
        self.realm = realm
        self.call_defaults = call_defaults or {}
        self.registry = resolve_reference(registry) if registry is not None else WAMPRegistry()
        self.ssl_context = ssl_context
        self.serializer = serializer if serializer is not None else CBORSerializer()
        self.auth_method = auth_method
        self.auth_id = auth_id
        self.auth_secret = auth_secret
        self.debug_app = debug_app
        self.debug_factory = debug_factory
        self.debug_code_paths = debug_code_paths

        self._lock = Lock()
        self._session = None  # type: AsphaltSession
        self._session_details = None  # type: SessionDetails
        self._register_topics({
            'realm_joined': SessionJoinEvent,
            'realm_left': SessionLeaveEvent
        })

    @coroutine
    def _register(self, procedure: Procedure):
        @coroutine
        def wrapper(*args, _call_details: CallDetails, **kwargs):
            ctx = CallContext(self.context, self._session_details, _call_details)
            try:
                retval = yield from procedure.handler(ctx, *args, **kwargs)
            except Exception as e:
                yield from ctx.dispatch('finished', e)
                raise

            yield from ctx.dispatch('finished', None)
            return retval

        options = RegisterOptions(details_arg='_call_details', **procedure.options)
        return (yield from self._session.register(wrapper, procedure.name, options))

    @coroutine
    def _subscribe(self, subscriber: Subscriber):
        @coroutine
        def wrapper(*args, _event_details: EventDetails, **kwargs):
            ctx = EventContext(self.context, self._session_details, _event_details)
            try:
                yield from subscriber.handler(ctx, *args, **kwargs)
            except Exception as e:
                yield from ctx.dispatch('finished', e)
                raise

            yield from ctx.dispatch('finished', None)

        options = SubscribeOptions(details_arg='_event_details', **subscriber.options)
        yield from self._session.subscribe(wrapper, subscriber.topic, options)

    @coroutine
    def start(self, ctx: Context):
        self.context = ctx
        if isinstance(self.ssl_context, str):
            self.ssl_context = yield from ctx.request_resource(SSLContext, self.ssl_context)
        if isinstance(self.serializer, str):
            self.serializer = yield from ctx.request_resource(Serializer, self.serializer)

    @asynchronous
    def map_exception(self, exc_class: type, error: str) -> None:
        """
        Map a Python exception to a WAMP error.

        :param exc_class: an exception class
        :param error: the WAMP error code

        """
        self.registry.map_exception(exc_class, error)
        if self._session is None:
            yield from self.connect()
        else:
            self._session.define(exc_class, error)

    @asynchronous
    def register_procedure(self, handler: Callable, name: str, **options) -> None:
        """
        Adds a procedure handler to the registry and attempts to register it on the router.

        :param handler: callable that handles calls for the given endpoint
        :param name: name of the endpoint to register (e.g. ``x.y.z``)
        :param options: extra keyword arguments to pass to
            :meth:`~.registry.WAMPRegistry.add_procedure`

        """
        procedure = self.registry.add_procedure(handler, name, **options)
        if self._session is None:
            yield from self.connect()  # this will automatically register the procedure
        else:
            yield from self._register(procedure)

    @asynchronous
    def subscribe(self, handler: Callable, topic: str, **options):
        """
        Adds a WAMP event subscriber to the registry and attempts to register it on the router.

        :param handler: the callable that is called when a message arrives
        :param topic: topic to subscribe to
        :param options: extra keyword arguments to pass to
            :meth:`~.registry.WAMPRegistry.add_subscriber`

        """
        subscriber = self.registry.add_subscriber(handler, topic, **options)
        if self._session is None:
            yield from self.connect()  # this will automatically register the subscriber
        else:
            yield from self._subscribe(subscriber)

    @asynchronous
    def publish(self, topic: str, *args, acknowledge: bool=False, exclude_me: bool=None,
                exclude: Iterable[int]=None, eligible: Iterable[int]=None, disclose_me: bool=None,
                **kwargs) -> Optional[int]:
        """
        Publish an event on the given topic.

        :param topic: the topic to publish on
        :param args: positional arguments to pass to subscribers
        :param acknowledge: ``True`` to wait until the router has acknowledged the event
        :param exclude_me: ``False`` to have the router also send the event back to the sender if
            it has any matching subscriptions
        :param exclude: iterable of WAMP session IDs to exclude from receiving this event
        :param eligible: list of WAMP session IDs eligible to receive this event
        :param disclose_me: ``True`` to disclose the publisher's identity to the subscribers
        :param kwargs: keyword arguments to pass to subscribers
        :return: publication ID (with ``acknowledge=True``)

        """
        assert check_argument_types()
        if self._session is None:
            yield from self.connect()

        kwargs['options'] = PublishOptions(acknowledge=acknowledge, exclude_me=exclude_me,
                                           exclude=list(exclude) if exclude else None,
                                           eligible=list(eligible) if eligible else None,
                                           disclose_me=disclose_me)
        retval = self._session.publish(topic, *args, **kwargs)
        if acknowledge:
            publication = yield from retval
            return publication.id

    @asynchronous
    def call(self, endpoint: str, *args, on_progress: Callable[..., None]=None,
             timeout: int=None, disclose_me: bool=None, **kwargs):
        """
        Call an RPC function.

        :param endpoint: name of the endpoint to call
        :param args: positional arguments to call the endpoint with
        :param on_progress: a callable that will receive progress reports from the endpoint
        :param timeout: timeout (in seconds) to wait for the completion of the call
        :param disclose_me: ``True`` to disclose the caller's identity to the callee
        :param kwargs: keyword arguments to call the endpoint with
        :return: the return value of the call
        :raises TimeoutError: if the call times out

        """
        assert check_argument_types()
        if self._session is None:
            yield from self.connect()

        if timeout is None:
            timeout = self.call_defaults.get('timeout')
        if disclose_me is None:
            disclose_me = self.call_defaults.get('disclose_me')

        options = CallOptions(on_progress=on_progress, timeout=timeout, disclose_me=disclose_me)
        return (yield from self._session.call(endpoint, *args, options=options, **kwargs))

    @asynchronous
    def connect(self) -> None:
        """
        Connect to the server and join the designated realm if not connected already.

        When joined, registers procedures and event subscriptions on the router from the registry.

        Does nothing if a connection has already been established.

        """
        @coroutine
        def leave_callback(session: AsphaltSession, leave_details: CloseDetails):
            self._session = self._session_details = None
            yield from self.dispatch('realm_left', leave_details)

        yield from self._lock.acquire()
        try:
            if self._session is None:
                from autobahn.websocket.protocol import parseWsUrl

                is_secure, host, port = parseWsUrl(self.url)[:3]
                ssl = (self.ssl_context or True) if is_secure else False
                join_future = Future()
                session_factory = partial(AsphaltSession, self.realm, self.auth_method,
                                          self.auth_id, self.auth_secret, self.debug_app,
                                          join_future)
                serializers = [wrap_serializer(self.serializer)]
                loop = txaio.config.loop = get_event_loop()
                transport_factory = WampWebSocketClientFactory(
                    session_factory, url=self.url, serializers=serializers, loop=loop,
                    debug=self.debug_factory, debugCodePaths=self.debug_code_paths)
                transport, protocol = yield from loop.create_connection(
                    transport_factory, host, port, ssl=ssl)

                try:
                    # Connection established; wait for the session to join the realm
                    self._session_details = yield from wait_for(join_future, 10, loop=loop)
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
                        done, not_done = yield from wait(tasks, loop=loop, timeout=10,
                                                         return_when=FIRST_EXCEPTION)
                        for task in done:
                            if task.exception():
                                raise task.exception()
                except Exception:
                    yield from self._session.leave()
                    self._session = self._session_details = None
                    raise

                self._session.on('leave', leave_callback)

                # Notify listeners that we've joined the realm
                yield from self.dispatch('realm_joined', self._session_details)
        finally:
            self._lock.release()

    @asynchronous
    def disconnect(self) -> None:
        """
        Leave the WAMP realm and disconnect from the server.

        This is a coroutine. Does nothing if not connected to a server.

        """
        if self._session:
            yield from self._session.leave()

    @property
    def session_id(self) -> Optional[int]:
        """
        Return the current WAMP session ID.

        :return: the session ID or ``None`` if not in a session.
        """
        return self._session_details.session if self._session_details else None
