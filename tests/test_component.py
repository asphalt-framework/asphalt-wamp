import ssl

from asphalt.core.context import Context
from asphalt.serialization.api import Serializer
from asphalt.serialization.serializers.json import JSONSerializer
import pytest

from asphalt.wamp.client import WAMPClient
from asphalt.wamp.component import WAMPComponent


@pytest.mark.asyncio
def test_single_client(event_loop):
    ctx = Context()
    component = WAMPComponent(ssl_context='default', serializer='default')
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    serializer = JSONSerializer()
    yield from ctx.publish_resource(serializer, types=[Serializer])
    yield from ctx.publish_resource(ssl_context)
    yield from component.start(ctx)

    assert isinstance(ctx.wamp, WAMPClient)
    assert ctx.wamp.ssl_context is ssl_context
    assert ctx.wamp.serializer is serializer


@pytest.mark.asyncio
def test_multiple_clients(event_loop):
    component = WAMPComponent(clients={
        'wamp1': {'url': 'ws://127.0.0.1/ws1'},
        'wamp2': {'url': 'ws://127.0.0.1/ws2'}
    })
    ctx = Context()
    yield from component.start(ctx)

    assert isinstance(ctx.wamp1, WAMPClient)
    assert isinstance(ctx.wamp2, WAMPClient)
    assert ctx.wamp1.url == 'ws://127.0.0.1/ws1'
    assert ctx.wamp2.url == 'ws://127.0.0.1/ws2'


def test_conflicting_config():
    exc = pytest.raises(ValueError, WAMPComponent, clients={'default': {}}, url='ws://1.2.3.4/')
    assert str(exc.value) == ('specify either a "clients" dictionary or the default client\'s '
                              'options directly, but not both')
