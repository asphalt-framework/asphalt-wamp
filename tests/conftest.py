import os

import pytest
import txaio
from async_generator import async_generator, yield_

from asphalt.core import Context
from asphalt.wamp.client import WAMPClient


@pytest.fixture(autouse=True)
def setup_txaio(event_loop):
    txaio.use_asyncio()
    txaio.config.loop = event_loop


@pytest.fixture
@async_generator
async def context():
    async with Context() as ctx:
        await yield_(ctx)


@pytest.fixture
@async_generator
async def wampclient(request, context):
    kwargs = getattr(request, 'param', {})
    kwargs.setdefault('host', os.getenv('CROSSBAR_HOST', '127.0.0.1'))
    kwargs.setdefault('max_reconnection_attempts', 0)
    client = WAMPClient(**kwargs)
    await client.start(context)
    await yield_(client)
    await client.stop()
