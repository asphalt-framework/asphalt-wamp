import ssl

from asphalt.core.context import Context
from asphalt.serialization.api import Serializer
from asphalt.serialization.serializers.json import JSONSerializer
import pytest

from asphalt.wamp.client import WAMPClient
from asphalt.wamp.component import WAMPComponent


@pytest.mark.asyncio
async def test_single_client(event_loop):
    ctx = Context()
    component = WAMPComponent(ssl='default', serializer='default')
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    serializer = JSONSerializer()
    ctx.publish_resource(serializer, types=[Serializer])
    ctx.publish_resource(ssl_context)
    await component.start(ctx)

    assert isinstance(ctx.wamp, WAMPClient)
    assert ctx.wamp.ssl is ssl_context
    assert ctx.wamp.serializer is serializer


@pytest.mark.asyncio
async def test_multiple_clients(event_loop):
    component = WAMPComponent(clients={
        'wamp1': {'url': 'ws://127.0.0.1/ws1'},
        'wamp2': {'url': 'ws://127.0.0.1/ws2'}
    }, auth_id='username')
    ctx = Context()
    await component.start(ctx)

    assert isinstance(ctx.wamp1, WAMPClient)
    assert isinstance(ctx.wamp2, WAMPClient)
    assert ctx.wamp1.url == 'ws://127.0.0.1/ws1'
    assert ctx.wamp2.url == 'ws://127.0.0.1/ws2'
    assert ctx.wamp1.auth_id == ctx.wamp2.auth_id == 'username'
