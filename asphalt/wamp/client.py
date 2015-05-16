from asyncio.tasks import wait_for

from typing import Callable, Iterable, Optional, Any
from asyncio import coroutine, gather, Future, get_event_loop
from asyncio.locks import Lock
from functools import partial
from ssl import SSLContext

from autobahn.asyncio.websocket import WampWebSocketClientFactory
from autobahn.asyncio.wamp import ApplicationSession
from autobahn.wamp.types import (
    ComponentConfig, SessionDetails, RegisterOptions, SubscribeOptions, EventDetails, CallDetails,
    PublishOptions, CallOptions, CloseDetails)
from asphalt.core.context import Context
from asphalt.core.event import EventSource
from asphalt.core.util import asynchronous
from asphalt.serialization.api import Serializer
from asphalt.wamp.serializers import wrap_serializer
from asphalt.wamp.utils import validate_handler
import txaio

from .context import EventContext, CallContext
from .events import SessionJoinEvent, SessionLeaveEvent
from .router import WAMPRouter

__all__ = ('WAMPClient',)


@coroutine
def procedure_wrapper(__handler: Callable, *args, __session_details: SessionDetails,
                      __parent_ctx: Context, __details: CallDetails, **kwargs):
    # Wrap the "progress" callable if it's present
    if __details.progress is not None:
        __details.progress = asynchronous(__details.progress)

    ctx = CallContext(__parent_ctx, __session_details, __details)
    try:
        retval = yield from __handler(ctx, *args, **kwargs)
    except Exception as e:
        yield from ctx.dispatch('finished', e)
        raise

    yield from ctx.dispatch('finished', None)
    return retval


@coroutine
def subscriber_wrapper(__handler: Callable, *args, __session_details: SessionDetails,
                       __parent_ctx: Context, __details: EventDetails, **kwargs):
    ctx = EventContext(__parent_ctx, __session_details, __details)
    try:
        yield from __handler(ctx, *args, **kwargs)
    except Exception as e:
        yield from ctx.dispatch('finished', e)
        raise

    yield from ctx.dispatch('finished', None)


class AsphaltSession(ApplicationSession):
    def __init__(self, realm: str, authid: Optional[str], authmethods: Optional[Iterable[str]],
                 debug: bool, join_future: Future):
        super().__init__(ComponentConfig(realm))
        self.debug_app = debug
        self.__authid = authid
        self.__authmethods = list(authmethods) if authmethods else None
        self.__join_future = join_future

    def onConnect(self):
        self.join(self.config.realm, self.__authmethods, self.__authid)

    def onJoin(self, details: SessionDetails):
        self.__join_future.set_result(details)


class WAMPClient(EventSource):
    """
    A WAMP client.

    Supported events:
      * ``realm_joined`` (:class:`~asphalt.wamp.events.SessionJoinEvent`): the client has joined
        the realm and has registered any procedures and subscribers on its assigned router
      * ``realm_left`` (:class:`~asphalt.wamp.events.SessionLeaveEvent`): the client has left
        the realm

    :ivar str realm: the WAMP realm
    :ivar str url: the WAMP URL
    """

    def __init__(self, context: Context, realm: str, url: str, ssl_context: Optional[SSLContext],
                 router: Optional[WAMPRouter], serializer: Optional[Serializer], debug_app: bool,
                 debug_factory: bool, debug_wamp: bool):
        super().__init__()
        self.context = context
        self.realm = realm
        self.url = url
        self.ssl_context = ssl_context
        self.router = router
        self.serializer = serializer
        self.debug_app = debug_app
        self.debug_factory = debug_factory
        self.debug_wamp = debug_wamp

        self._lock = Lock()
        self._session = None  # type: AsphaltSession
        self._session_details = None  # type: SessionDetails
        self._register_topics({
            'realm_joined': SessionJoinEvent,
            'realm_left': SessionLeaveEvent
        })

    @asynchronous
    def publish(self, topic: str, *args, acknowledge: bool=False, exclude_me: bool=None,
                exclude: Iterable[int]=None, eligible: Iterable[int]=None, disclose_me: bool=None,
                **kwargs):
        """
        Publish a message.

        :param topic: the topic to publish on
        :param args: positional arguments to pass to subscribers
        :param acknowledge: ``True`` to wait until the router has acknowledged the event
        :param exclude_me: ``False`` to have the router also send the event back to the sender if
            it has any matching subscriptions
        :param exclude: iterable of WAMP session IDs to exclude from receiving this event
        :param eligible: list of WAMP session IDs eligible to receive this event
        :param disclose_me: ``True`` to disclose the publisher's identity to the subscribers
        :param kwargs: keyword arguments to pass to subscribers
        :return: publication ID (if ``acknowledge``=`True``)

        """
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
    def subscribe(self, handler: Callable[..., None], topic: str, match: str='exact'):
        """
        Subscribe to a topic.

        .. seealso:: `How subscriptions work <http://crossbar.io/docs/How-Subscriptions-Work/>`_
        .. seealso:: `Pattern based subscriptions
            <http://crossbar.io/docs/Pattern-Based-Subscriptions/>`_

        :param handler: the callable that is called when a message arrives
        :param topic: topic to subscribe to
        :param match: one of ``exact``, ``prefix`` or ``wildcard``

        """
        if self._session is None:
            yield from self.connect()

        validate_handler(handler, 'subscriber')
        options = SubscribeOptions(match=match, details_arg='__details')
        wrapped = partial(subscriber_wrapper, handler, __parent_ctx=self.context,
                          __session_details=self._session_details)
        yield from self._session.subscribe(wrapped, topic, options)

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
        if self._session is None:
            yield from self.connect()

        options = CallOptions(on_progress=on_progress, timeout=timeout, disclose_me=disclose_me)
        return (yield from self._session.call(endpoint, *args, options=options, **kwargs))

    @asynchronous
    def register(self, handler: Callable, endpoint: str, match: str='exact', invoke: str='single'):
        """
        Register a procedure handler.

        .. seealso:: `How registrations work <http://crossbar.io/docs/How-Registrations-Work/>`_
        .. seealso:: `Pattern based registrations
            <http://crossbar.io/docs/Pattern-Based-Registrations/>`_
        .. seealso:: `Shared registrations <http://crossbar.io/docs/Shared-Registrations/>`_

        :param handler: callable that handles calls for the given endpoint
        :param endpoint: name of the endpoint to register
        :param match: one of ``exact``, ``prefix``, ``wildcard``
        :param invoke: one of ``single``, ``roundrobin``, ``random``, ``first``, ``last``

        """
        if self._session is None:
            yield from self.connect()

        validate_handler(handler, 'procedure handler')
        options = RegisterOptions(match=match, invoke=invoke, details_arg='__details')
        wrapped = partial(procedure_wrapper, handler, __parent_ctx=self.context,
                          __session_details=self._session_details)
        return (yield from self._session.register(wrapped, endpoint, options))

    @asynchronous
    def map_exception(self, exc_class: type, error: str):
        """
        Map a Python exception to a WAMP error.

        :param exc_class: an exception class
        :param error: the WAMP error code

        """
        if self._session is None:
            yield from self.connect()

        self._session.define(exc_class, error)

    @asynchronous
    def connect(self):
        yield from self._lock.acquire()
        try:
            if self._session is None:
                from autobahn.websocket.protocol import parseWsUrl

                is_secure, host, port = parseWsUrl(self.url)[:3]
                ssl = (self.ssl_context or True) if is_secure else False
                join_future = Future()
                session_factory = partial(AsphaltSession, self.realm, None, None, self.debug_app,
                                          join_future)
                serializers = [wrap_serializer(self.serializer)] if self.serializer else None
                loop = txaio.config.loop = get_event_loop()
                transport_factory = WampWebSocketClientFactory(
                    session_factory, url=self.url, serializers=serializers, loop=loop,
                    debug=self.debug_factory, debug_wamp=self.debug_wamp)
                transport, protocol = yield from loop.create_connection(
                    transport_factory, host, port, ssl=ssl)

                # Connection established; wait for the session to join the realm
                self._session_details = yield from wait_for(join_future, 5, loop=loop)
                self._session = protocol._session

                # Notify listeners that we've joined the realm
                yield from self.dispatch('realm_joined', self._session_details)

                self._session.on('leave', self._leave_callback)
        finally:
            self._lock.release()

        return self._session

    @asynchronous
    def disconnect(self):
        if self._session:
            yield from self._session.leave()

    @coroutine
    def _leave_callback(self, session: AsphaltSession, leave_details: CloseDetails):
        self._session = self._session_details = None
        yield from self.dispatch('realm_left', leave_details)
