import asyncio
import queue

import pytest

from asphalt.core.concurrency import blocking, asynchronous
from asphalt.wamp.client import WAMPClient
from asphalt.wamp.events import SessionJoinEvent, SessionLeaveEvent


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


@pytest.mark.asyncio
def test_register_call_async(wampclient: WAMPClient):
    @asyncio.coroutine
    def add(ctx, x, y):
        return x + y

    yield from wampclient.register(add, 'test.add')
    result = yield from wampclient.call('test.add', 2, 3)
    assert result == 5


@pytest.mark.asyncio
def test_register_call_progress_async(wampclient: WAMPClient):
    @asyncio.coroutine
    def progressive_procedure(ctx, start, end):
        for value in range(start, end):
            ctx.progress(value)
        return end

    progress_values = []
    yield from wampclient.register(progressive_procedure, 'test.progressive')
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

    wampclient.register(add, 'test.add')
    result = wampclient.call('test.add', 2, 3)
    assert result == 5


@pytest.mark.asyncio
def test_publish_subscribe_async(wampclient: WAMPClient):
    @asynchronous
    def subscriber(ctx, *args):
        yield from q.put(args)
        raise Exception()

    q = asyncio.Queue()
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


@pytest.mark.asyncio
def test_map_exception(wampclient: WAMPClient):
    class TestException(Exception):
        pass

    @asyncio.coroutine
    def error(ctx):
        raise TestException

    yield from wampclient.map_exception(TestException, 'test.exception')
    yield from wampclient.register(error, 'test.error')
    with pytest.raises(TestException):
        yield from wampclient.call('test.error')
