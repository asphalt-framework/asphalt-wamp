from autobahn.wamp.types import SessionDetails, CloseDetails
from asphalt.core.context import Context
import pytest

from asphalt.wamp.client import WAMPClient
from asphalt.wamp.events import SessionJoinEvent, SessionLeaveEvent


@pytest.fixture
def client():
    return WAMPClient(Context(), 'default', 'ws://localhost/ws', None, None, None, False, False,
                      False)


def test_join_event(client):
    details = SessionDetails('default', 5)
    event = SessionJoinEvent(client, 'realm_joined', details)
    assert event.session_id == 5


def test_leave_event(client):
    details = CloseDetails('reason', 'message')
    event = SessionLeaveEvent(client, 'realm_left', details)
    assert event.reason == 'reason'
    assert event.message == 'message'
