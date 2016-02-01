import asyncio
import queue
from asyncio.coroutines import coroutine

from autobahn.wamp.types import Challenge
from asphalt.core.concurrency import blocking, asynchronous
import pytest

from asphalt.wamp.client import WAMPClient, AsphaltSession, AuthenticationError
from asphalt.wamp.events import SessionJoinEvent, SessionLeaveEvent


class TestAsphaltSession:
    def test_challenge_mismatch(self):
        session = AsphaltSession('default', 'ticket', 'foo', 'bar', True, asyncio.Future())
        challenge = Challenge('wampcra')
        exc = pytest.raises(Exception, session.onChallenge, challenge)
        assert str(exc.value) == ('Expected authentication method "ticket" but received a '
                                  '"wampcra" challenge instead')

    def test_ticket_challenge(self):
        session = AsphaltSession('default', 'ticket', 'foo', 'bar', True, asyncio.Future())
        challenge = Challenge('ticket')
        assert session.onChallenge(challenge) == 'bar'

    def test_wampcra_challenge(self):
        session = AsphaltSession('default', 'wampcra', 'foo', 'bar', True, asyncio.Future())
        challenge = Challenge('wampcra', {'challenge': b'\xff\x00345jfsdf'})
        retval = session.onChallenge(challenge)
        assert isinstance(retval, bytes)

    def test_wampcra_salted_challenge(self):
        session = AsphaltSession('default', 'wampcra', 'foo', 'bar', True, asyncio.Future())
        challenge = Challenge('wampcra', {'challenge': b'\xff\x00345jfsdf', 'salt': '5ihod',
                                          'iterations': 5, 'keylen': 32})
        retval = session.onChallenge(challenge)
        assert isinstance(retval, bytes)


@pytest.mark.asyncio
def test_client_events(wampclient: WAMPClient):
    def listener(event):
        events.append(event)

    events = []
    wampclient.add_listener('realm_joined', listener)
    wampclient.add_listener('realm_left', listener)
    yield from wampclient.connect()
    yield from wampclient.disconnect()

    assert len(events) == 2
    assert isinstance(events[0], SessionJoinEvent)
    assert isinstance(events[1], SessionLeaveEvent)


@pytest.mark.parametrize('connect_first', [False, True])
@pytest.mark.asyncio
def test_call_async(wampclient: WAMPClient, connect_first):
    if connect_first:
        yield from wampclient.connect()

    result = yield from wampclient.call('wamp.session.count')
    assert result == 1


@pytest.mark.parametrize('wampclient', [{'call_defaults': {'disclose_me': True}}], indirect=True)
@pytest.mark.asyncio
def test_call_defaults(wampclient: WAMPClient):
    @asynchronous
    @coroutine
    def whoami(ctx):
        return ctx.session_id

    yield from wampclient.register_procedure(whoami, 'test.whoami')
    result = yield from wampclient.call('test.whoami')
    assert result == wampclient.session_id


@pytest.mark.asyncio
def test_register_call_progress_async(wampclient: WAMPClient):
    @asyncio.coroutine
    def progressive_procedure(ctx, start, end):
        for value in range(start, end):
            ctx.progress(value)
        return end

    progress_values = []
    yield from wampclient.register_procedure(progressive_procedure, 'test.progressive')
    result = yield from wampclient.call('test.progressive', 2, 6,
                                        on_progress=progress_values.append)
    assert progress_values == [2, 3, 4, 5]
    assert result == 6


@pytest.mark.asyncio
@blocking
def test_register_call_blocking(wampclient: WAMPClient):
    @blocking
    def add(ctx, x, y):
        return x + y

    wampclient.register_procedure(add, 'test.add')
    result = wampclient.call('test.add', 2, 3)
    assert result == 5


@pytest.mark.parametrize('wampclient', [
    {'auth_method': 'wampcra', 'auth_id': 'testuser', 'auth_secret': 'testpass'}
], indirect=True)
@pytest.mark.asyncio
def test_auth_wampcra(wampclient: WAMPClient):
    yield from wampclient.connect()
    result = yield from wampclient.call('wamp.session.get', wampclient.session_id)
    assert result['authid'] == 'testuser'


@pytest.mark.parametrize('wampclient', [
    {'auth_method': 'ticket', 'auth_id': 'device1', 'auth_secret': 'abc123'}
], indirect=True)
@pytest.mark.asyncio
def test_auth_ticket(wampclient: WAMPClient):
    yield from wampclient.connect()
    result = yield from wampclient.call('wamp.session.get', wampclient.session_id)
    assert result['authid'] == 'device1'


@pytest.mark.parametrize('wampclient', [
    {'auth_method': 'ticket', 'auth_id': 'device1', 'auth_secret': 'abc124'}
], indirect=True)
@pytest.mark.asyncio
def test_auth_failure(wampclient: WAMPClient):
    with pytest.raises(AuthenticationError) as e:
        yield from wampclient.connect()

    assert str(e.value) == 'ticket in static WAMP-Ticket authentication is invalid'


@pytest.mark.asyncio
def test_publish_autoconnect(wampclient: WAMPClient):
    result = yield from wampclient.publish('test.topic', acknowledge=True)
    assert result


@pytest.mark.parametrize('connect_first', [False, True])
@pytest.mark.asyncio
def test_publish_subscribe_async(wampclient: WAMPClient, connect_first):
    @asynchronous
    def subscriber(ctx, *args):
        yield from q.put(args)
        raise Exception()

    q = asyncio.Queue()
    if connect_first:
        yield from wampclient.connect()

    yield from wampclient.subscribe(subscriber, 'test.topic')
    publication_id = yield from wampclient.publish('test.topic', 2, 3, exclude_me=False,
                                                   acknowledge=True)
    assert isinstance(publication_id, int)
    event = yield from asyncio.wait_for(q.get(), 2)
    assert event == (2, 3)


@pytest.mark.asyncio
@blocking
def test_publish_subscribe_blocking(wampclient: WAMPClient):
    @blocking
    def subscriber(ctx, *args):
        q.put(args)

    q = queue.Queue()
    wampclient.subscribe(subscriber, 'test.topic')
    publication_id = wampclient.publish('test.topic', 2, 3, exclude_me=False, acknowledge=True)
    assert isinstance(publication_id, int)
    event = q.get(timeout=2)
    assert event == (2, 3)


@pytest.mark.parametrize('connect_first', [False, True])
@pytest.mark.asyncio
def test_map_exception(wampclient: WAMPClient, connect_first):
    class TestException(Exception):
        pass

    @asyncio.coroutine
    def error(ctx):
        raise TestException

    if connect_first:
        yield from wampclient.connect()

    yield from wampclient.map_exception(TestException, 'test.exception')
    yield from wampclient.register_procedure(error, 'test.error')
    with pytest.raises(TestException):
        yield from wampclient.call('test.error')


@pytest.mark.asyncio
def test_join_failure(wampclient: WAMPClient):
    """
    Tests that a failure in registering the registry's procedures causes the connection to be
    terminated.

    """
    with pytest.raises(AssertionError):
        yield from wampclient.register_procedure(lambda ctx: None, 'blah', invoke='blabla')

    assert wampclient.session_id is None


def test_session_id_not_connected(wampclient: WAMPClient):
    assert wampclient.session_id is None
