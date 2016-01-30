from autobahn.wamp.types import CallDetails, SessionDetails, EventDetails

from asphalt.core.context import Context
from asphalt.core.concurrency import asynchronous


class CallContext(Context):
    """
    Context class for procedure calls.

    Procedure call handlers are passed an instance of this class as the first argument.

    :ivar int session_id: our own WAMP session ID
    :ivar Optional[int] caller_session_id: WAMP session ID of the caller, if disclosed
    :ivar Optional[Callable] progress: a callable through which the handler can send
        progress information to the caller
    :ivar str procedure: absolute name of the procedure
    """

    def __init__(self, parent: Context, session_details: SessionDetails,
                 call_details: CallDetails, **kwargs):
        super().__init__(parent, **kwargs)
        self.session_id = session_details.session
        self.caller_session_id = call_details.caller
        self.progress = asynchronous(call_details.progress) if call_details.progress else None
        self.procedure = call_details.procedure


class EventContext(Context):
    """
    Context class for WAMP events.

    Event subscribers are passed an instance of this class as the first argument.

    :ivar int session_id: our own WAMP session ID
    :ivar int publication_id: publication ID of the event
    :ivar int publisher_session_id: WAMP session ID of the publisher, if disclosed
    :ivar str topic: the exact topic the event was received on
    """

    def __init__(self, parent: Context, session_details: SessionDetails,
                 event_details: EventDetails, **kwargs):
        super().__init__(parent, **kwargs)
        self.session_id = session_details.session
        self.publication_id = event_details.publication
        self.publisher_session_id = event_details.publisher
        self.topic = event_details.topic
