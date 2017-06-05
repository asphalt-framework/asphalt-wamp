from autobahn.wamp.types import SessionDetails, CloseDetails

from asphalt.core import Event

__all__ = ('SessionJoinEvent', 'SessionLeaveEvent')


class SessionJoinEvent(Event):
    """
    Signals that the client has joined the WAMP realm on the router.

    :ivar details: the autobahn-provided session details
    :vartype details: ~autobahn.wamp.types.SessionDetails
    """

    __slots__ = 'details'

    def __init__(self, source, topic: str, session_details: SessionDetails):
        super().__init__(source, topic)
        self.details = session_details


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
