import asyncio
import os
import re

import pytest
from autobahn.wamp import ApplicationError

from asphalt.core import executor
from autobahn.wamp.types import Challenge, PublishOptions, CallOptions

from asphalt.wamp.client import WAMPClient, AsphaltSession, ConnectionError
from asphalt.wamp.events import SessionJoinEvent, SessionLeaveEvent


class TestAsphaltSession:
    @pytest.fixture
    def session(self, request, event_loop):
        client = WAMPClient(realm='default', auth_method=request.param, auth_id='foo',
                            auth_secret='bar')
        return AsphaltSession(client, event_loop.create_future())

    @pytest.mark.parametrize('future_done', [False, True])
    @pytest.mark.asyncio
    async def test_on_disconnect(self, event_loop, wampclient, future_done):
        future = event_loop.create_future()
        session = AsphaltSession(wampclient, future)
        if future_done:
            future.set_result(None)
            session.onDisconnect()
            assert (await future) is None
        else:
            with pytest.raises(ConnectionError) as exc:
                session.onDisconnect()
                await future

            exc.match('connection closed unexpectedly')

    @pytest.mark.parametrize('session', ['ticket'], indirect=['session'])
    def test_challenge_mismatch(self, session):
        challenge = Challenge('wampcra')
        exc = pytest.raises(ConnectionError, session.onChallenge, challenge)
        assert exc.match('expected authentication method "ticket" but received a "wampcra" '
                         'challenge instead')

    @pytest.mark.parametrize('session', ['ticket'], indirect=['session'])
    def test_ticket_challenge(self, session):
        challenge = Challenge('ticket')
        assert session.onChallenge(challenge) == 'bar'

    @pytest.mark.parametrize('session', ['wampcra'], indirect=['session'])
    def test_wampcra_challenge(self, session):
        challenge = Challenge('wampcra', {'challenge': b'\xff\x00345jfsdf'})
        retval = session.onChallenge(challenge)
        assert isinstance(retval, bytes)

    @pytest.mark.parametrize('session', ['wampcra'], indirect=['session'])
    def test_wampcra_salted_challenge(self, session):
        challenge = Challenge('wampcra', {'challenge': b'\xff\x00345jfsdf', 'salt': '5ihod',
                                          'iterations': 5, 'keylen': 32})
        retval = session.onChallenge(challenge)
        assert isinstance(retval, bytes)


class TestWAMPClient:
    @pytest.fixture
    def otherclient(self, request, event_loop, context):
        kwargs = getattr(request, 'param', {})
        kwargs.setdefault('host', os.getenv('CROSSBAR_HOST', 'localhost'))
        kwargs.setdefault('max_reconnection_attempts', 0)
        client = WAMPClient(**kwargs)
        event_loop.run_until_complete(client.start(context))
        yield client
        event_loop.run_until_complete(client.close())

    @pytest.mark.asyncio
    async def test_client_events(self, wampclient: WAMPClient):
        def listener(event):
            events.append(event)

        events = []
        wampclient.realm_joined.connect(listener)
        wampclient.realm_left.connect(listener)
        await wampclient.connect()
        await wampclient.close()

        assert len(events) == 2
        assert isinstance(events[0], SessionJoinEvent)
        assert isinstance(events[1], SessionLeaveEvent)

    @pytest.mark.parametrize('connect_first', [False, True])
    @pytest.mark.asyncio
    async def test_call(self, wampclient: WAMPClient, connect_first):
        if connect_first:
            await wampclient.connect()

        result = await wampclient.call('wamp.session.count')
        assert result == 1

    @pytest.mark.asyncio
    async def test_register_call_progress(self, wampclient: WAMPClient):
        async def progressive_procedure(ctx, start, end):
            for value in range(start, end):
                ctx.progress(value)
            return end

        progress_values = []
        await wampclient.register(progressive_procedure, 'test.progressive')
        result = await wampclient.call('test.progressive', 2, 6,
                                       options=CallOptions(on_progress=progress_values.append))
        assert progress_values == [2, 3, 4, 5]
        assert result == 6

    @pytest.mark.asyncio
    async def test_register_call_blocking(self, wampclient: WAMPClient):
        @executor
        def add(ctx, x, y):
            return x + y

        await wampclient.register(add, 'test.add')
        result = await wampclient.call('test.add', 2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_register_call_plain(self, wampclient: WAMPClient):
        def add(ctx, x, y):
            return x + y

        await wampclient.register(add, 'test.add')
        result = await wampclient.call('test.add', 2, 3)
        assert result == 5

    @pytest.mark.parametrize('wampclient', [
        {'auth_method': 'wampcra', 'auth_id': 'testuser', 'auth_secret': 'testpass'}
    ], indirect=True)
    @pytest.mark.asyncio
    async def test_auth_wampcra(self, wampclient: WAMPClient):
        await wampclient.connect()
        result = await wampclient.call('wamp.session.get', wampclient.session_id)
        assert result['authid'] == wampclient.details.authid == 'testuser'

    @pytest.mark.parametrize('wampclient', [
        {'auth_method': 'ticket', 'auth_id': 'device1', 'auth_secret': 'abc123'}
    ], indirect=True)
    @pytest.mark.asyncio
    async def test_auth_ticket(self, wampclient: WAMPClient):
        await wampclient.connect()
        result = await wampclient.call('wamp.session.get', wampclient.session_id)
        assert result['authid'] == wampclient.details.authid == 'device1'

    @pytest.mark.parametrize('wampclient', [
        {'auth_method': 'ticket', 'auth_id': 'device1', 'auth_secret': 'abc124'}
    ], indirect=True)
    @pytest.mark.asyncio
    async def test_auth_failure(self, wampclient: WAMPClient):
        with pytest.raises(ConnectionError) as exc:
            await wampclient.connect()

        assert exc.match('ticket in static WAMP-Ticket authentication is invalid')

    @pytest.mark.asyncio
    async def test_publish_autoconnect(self, wampclient: WAMPClient):
        result = await wampclient.publish('test.topic', options=PublishOptions(acknowledge=True))
        assert result

    @pytest.mark.parametrize('connect_first', [False, True])
    @pytest.mark.asyncio
    async def test_publish_subscribe(self, wampclient: WAMPClient, connect_first):
        async def subscriber(ctx, *args):
            await q.put(args)
            raise Exception()

        q = asyncio.Queue()
        if connect_first:
            await wampclient.connect()

        await wampclient.subscribe(subscriber, 'test.topic')
        publication_id = await wampclient.publish(
            'test.topic', 2, 3, options=PublishOptions(exclude_me=False, acknowledge=True))
        assert isinstance(publication_id, int)
        event = await asyncio.wait_for(q.get(), 2)
        assert event == (2, 3)

    @pytest.mark.parametrize('connect_first', [False, True])
    @pytest.mark.asyncio
    async def test_map_exception(self, wampclient: WAMPClient, connect_first):
        class TestException(Exception):
            pass

        async def error(ctx):
            raise TestException

        if connect_first:
            await wampclient.connect()

        wampclient.map_exception(TestException, 'test.exception')
        await wampclient.register(error, 'test.error')
        with pytest.raises(TestException):
            await wampclient.call('test.error')

    @pytest.mark.asyncio
    async def test_connect_procedure_registration_failure(self, wampclient: WAMPClient,
                                                          otherclient: WAMPClient):
        """
        Test that a failure in registering the registry's procedures causes the connection attempt
        to fail.

        """
        await otherclient.register(lambda ctx: None, 'blah')
        with pytest.raises(ApplicationError):
            await wampclient.register(lambda ctx: None, 'blah')

        assert wampclient.session_id is None

    @pytest.mark.parametrize('wampclient', [
        {'port': 8081, 'max_reconnection_attempts': 1, 'reconnect_delay': 0.3}], indirect=True)
    @pytest.mark.asyncio
    async def test_connect_retry(self, wampclient: WAMPClient, caplog):
        """Test that if the client can't connect, it will retry after a delay."""
        with pytest.raises(ConnectionRefusedError):
            await wampclient.connect()

        messages = [record.message for record in caplog.records
                    if record.name == 'asphalt.wamp.client' and
                    record.message.startswith('Connection failed')]
        assert len(messages) == 1
        assert re.fullmatch("Connection failed \(attempt 1\): ConnectionRefusedError\(.+?\); "
                            "reconnecting in 0.3 seconds", messages[0])

    @pytest.mark.asyncio
    async def test_close_wait_handlers(self, event_loop, wampclient: WAMPClient,
                                       otherclient: WAMPClient, caplog):
        """
        Test that WAMPClient.close() waits for any running handler tasks to finish before
        disconnecting from the router.

        """
        async def sleep_subscriber(ctx):
            nonlocal close_task
            close_task = event_loop.create_task(wampclient.close())
            await asyncio.sleep(0.3)

        async def sleep_sum(ctx, x, y):
            await asyncio.sleep(0.3)
            return x + y

        close_task = None
        await wampclient.register(sleep_sum)
        await wampclient.subscribe(sleep_subscriber, 'testtopic')

        await otherclient.publish('testtopic', options=PublishOptions(acknowledge=True))
        result = await otherclient.call('sleep_sum', 1, 2)
        assert result == 3
        await close_task

        messages = [record.message for record in caplog.records
                    if record.name == 'asphalt.wamp.client' and
                    record.message.startswith('Waiting for')]
        assert messages == ['Waiting for 2 WAMP subscription/procedure handler tasks to finish']

    @pytest.mark.asyncio
    async def test_connect_twice(self, wampclient: WAMPClient):
        """
        Test that when connect() is called while connected, it just returns a Future that resolves
        immediately.

        """
        retval = wampclient.connect()
        assert isinstance(retval, asyncio.Task)
        await retval

        retval = wampclient.connect()
        assert isinstance(retval, asyncio.Future)
        await retval

    def test_session_id_not_connected(self, wampclient: WAMPClient):
        assert wampclient.session_id is None

    def test_session_details_not_connected(self, wampclient: WAMPClient):
        assert wampclient.details is None
