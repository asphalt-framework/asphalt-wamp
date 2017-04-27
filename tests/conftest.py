import asyncio
import os

import pytest
import txaio
from asphalt.core import Context

from asphalt.wamp.client import WAMPClient


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    txaio.use_asyncio()
    txaio.config.loop = loop
    yield loop
    loop.close()


@pytest.fixture
def context(event_loop):
    with Context() as ctx:
        yield ctx


@pytest.fixture
def wampclient(request, event_loop, context):
    kwargs = getattr(request, 'param', {})
    kwargs.setdefault('host', os.getenv('CROSSBAR_HOST', 'localhost'))
    kwargs.setdefault('max_reconnection_attempts', 0)
    client = WAMPClient(**kwargs)
    event_loop.run_until_complete(client.start(context))
    yield client
    event_loop.run_until_complete(client.close())
