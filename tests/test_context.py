from autobahn.wamp.request import Registration, Subscription
from autobahn.wamp.types import SessionDetails, CallDetails, EventDetails
from asphalt.core.context import Context

from asphalt.wamp.context import CallContext, EventContext


def test_call_context():
    def progress(arg):
        pass

    parent = Context()
    session_details = SessionDetails('default', 5)
    registration = Registration(5420493024, 12313423, lambda: None, 'foo.bar')
    call_details = CallDetails(registration, progress=progress, caller=8, caller_authid='user',
                               caller_authrole='role', procedure='procedurename')
    context = CallContext(parent, session_details, call_details)

    assert context.session_id == 5
    assert context.caller_session_id == 8
    assert context.caller_auth_id == 'user'
    assert context.caller_auth_role == 'role'
    assert context.procedure == 'procedurename'
    assert context.enc_algo is None
    assert context.progress is progress


def test_event_context():
    parent = Context()
    session_details = SessionDetails('default', 5)
    subscription = Subscription(1230643, 'foo.bar', 5420493024, lambda: None)
    event_details = EventDetails(subscription, publication=15, publisher=8,
                                 publisher_authid='user', publisher_authrole='role', topic='topic')
    context = EventContext(parent, session_details, event_details)

    assert context.session_id == 5
    assert context.publisher_session_id == 8
    assert context.publisher_auth_id == 'user'
    assert context.publisher_auth_role == 'role'
    assert context.publication_id == 15
    assert context.topic == 'topic'
    assert context.enc_algo is None
