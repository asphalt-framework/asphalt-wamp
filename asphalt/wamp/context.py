from autobahn.wamp.types import CallDetails, SessionDetails, EventDetails

from asphalt.core import Context

__all__ = ('CallContext', 'EventContext')


class CallContext(Context):
    """
    Context class for procedure calls.

    Procedure call handlers are passed an instance of this class as the first argument.

    :ivar int session_id: our own WAMP session ID
    :ivar Optional[Callable] progress: a callable through which the handler can send
        progress information to the caller
    :ivar Optional[int] caller_session_id: WAMP session ID of the caller (if disclosed)
    :ivar Optional[str] caller_auth_id: WAMP authentication ID (username) of the caller
        (if disclosed)
    :ivar Optional[str] caller_auth_role: WAMP authentication role of the caller (if disclosed)
    :ivar Optional[str] procedure: the actual name of the procedure (when using a pattern based
        registration)
    :ivar Optional[str] enc_algo: payload encryption algorithm that was in use, if any
        (e.g. `cryptobox`, or a custom algorithm)
    """

    def __init__(self, parent: Context, session_details: SessionDetails,
                 call_details: CallDetails, **kwargs):
        super().__init__(parent, **kwargs)
        self.session_id = session_details.session
        self.progress = call_details.progress
        self.caller_session_id = call_details.caller
        self.caller_auth_id = call_details.caller_authid
        self.caller_auth_role = call_details.caller_authrole
        self.procedure = call_details.procedure
        self.enc_algo = call_details.enc_algo


class EventContext(Context):
    """
    Context class for WAMP events.

    Event subscribers are passed an instance of this class as the first argument.

    :ivar int session_id: our own WAMP session ID
    :ivar int publication_id: publication ID of the event
    :ivar int publisher_session_id: WAMP session ID of the publisher, if disclosed
    :ivar Optional[str] publisher_auth_id: WAMP authentication ID (username) of the publisher
        (if disclosed)
    :ivar Optional[str] publisher_auth_role: WAMP authentication role of the publisher
        (if disclosed)
    :ivar str topic: the exact topic the event was received on
    :ivar Optional[str] enc_algo: payload encryption algorithm that was in use, if any
        (e.g. `cryptobox`, or a custom algorithm)
    """

    def __init__(self, parent: Context, session_details: SessionDetails,
                 event_details: EventDetails, **kwargs):
        super().__init__(parent, **kwargs)
        self.session_id = session_details.session
        self.publication_id = event_details.publication
        self.publisher_session_id = event_details.publisher
        self.publisher_auth_id = event_details.publisher_authid
        self.publisher_auth_role = event_details.publisher_authrole
        self.topic = event_details.topic
        self.enc_algo = event_details.enc_algo
