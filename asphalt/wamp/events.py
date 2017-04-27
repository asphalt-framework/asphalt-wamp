from autobahn.wamp.types import SessionDetails, CloseDetails

from asphalt.core import Event

__all__ = ('SessionJoinEvent', 'SessionLeaveEvent')


class SessionJoinEvent(Event):
    """
    Signals that the client has joined the WAMP realm on the router.

    :ivar int session_id: session ID on the WAMP router
    """

    __slots__ = 'session_id'

    def __init__(self, source, topic: str, session_details: SessionDetails):
        super().__init__(source, topic)
        self.session_id = session_details.session


class SessionLeaveEvent(Event):
    """
    Signals that the client has left the WAMP realm on the router.

    :ivar str reason: the reason why the client left the realm
    :ivar str message: the closing message
    """

    __slots__ = 'reason', 'message'

    def __init__(self, source, topic: str, close_details: CloseDetails):
        super().__init__(source, topic)
        self.reason = close_details.reason
        self.message = close_details.message
