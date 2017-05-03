import ssl

from asphalt.serialization.api import Serializer
from asphalt.serialization.serializers.json import JSONSerializer
import pytest

from asphalt.wamp.client import WAMPClient
from asphalt.wamp.component import WAMPComponent
from asphalt.wamp.registry import WAMPRegistry


@pytest.mark.asyncio
async def test_single_client(context):
    tls_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.add_resource(tls_context)

    serializer = JSONSerializer()
    context.add_resource(serializer, types=[Serializer])

    registry = WAMPRegistry()
    context.add_resource(registry)

    component = WAMPComponent(tls_context='default', serializer='default', registry='default')
    await component.start(context)

    assert isinstance(context.wamp, WAMPClient)
    assert context.wamp.tls_context is tls_context
    assert context.wamp.serializer is serializer


@pytest.mark.asyncio
async def test_multiple_clients(context):
    component = WAMPComponent(clients={
        'wamp1': {'host': '192.168.10.1', 'port': 8085},
        'wamp2': {'path': '/'}
    }, auth_id='username')
    await component.start(context)

    assert isinstance(context.wamp1, WAMPClient)
    assert isinstance(context.wamp2, WAMPClient)
    assert context.wamp1.host == '192.168.10.1'
    assert context.wamp1.port == 8085
    assert context.wamp1.path == '/ws'
    assert context.wamp2.host == 'localhost'
    assert context.wamp2.port == 8080
    assert context.wamp2.path == '/'
    assert context.wamp1.auth_id == context.wamp2.auth_id == 'username'
