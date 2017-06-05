from autobahn.wamp.types import SessionDetails, CloseDetails

from asphalt.wamp.events import SessionJoinEvent, SessionLeaveEvent


def test_join_event(wampclient):
    details = SessionDetails('default', 5)
    event = SessionJoinEvent(wampclient, 'realm_joined', details)
    assert event.details.session == 5


def test_leave_event(wampclient):
    details = CloseDetails('reason', 'message')
    event = SessionLeaveEvent(wampclient, 'realm_left', details)
    assert event.reason == 'reason'
    assert event.message == 'message'
