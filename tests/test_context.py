from autobahn.wamp.types import SessionDetails, CallDetails, EventDetails
from asphalt.core.context import Context

from asphalt.wamp.context import CallContext, EventContext


def test_call_context():
    def progress(arg):
        pass

    parent = Context()
    session_details = SessionDetails('default', 5)
    call_details = CallDetails(progress, 8, 'procedurename')
    context = CallContext(parent, session_details, call_details)

    assert context.session_id == 5
    assert context.caller_session_id == 8
    assert context.procedure == 'procedurename'
    assert context.progress.__wrapped__ is progress


def test_event_context():
    parent = Context()
    session_details = SessionDetails('default', 5)
    event_details = EventDetails(15, 8, 'topic')
    context = EventContext(parent, session_details, event_details)

    assert context.session_id == 5
    assert context.publisher_session_id == 8
    assert context.publication_id == 15
    assert context.topic == 'topic'
