from autobahn.wamp import serializer as autobahn
from asphalt.serialization.serializers.cbor import CBORSerializer
from asphalt.serialization.serializers.json import JSONSerializer
from asphalt.serialization.serializers.msgpack import MsgpackSerializer
from asphalt.serialization.serializers.yaml import YAMLSerializer
import pytest

from asphalt.wamp.serializers import wrap_serializer, ObjectSerializerWrapper


@pytest.fixture(params=[JSONSerializer, MsgpackSerializer, CBORSerializer],
                ids=['json', 'msgpack', 'cbor'])
def serializer(request):
    return request.param()


@pytest.mark.parametrize('value', [
    'text', 123, ['a', 1, 2.5, True], {'x': 'a', 'y': 2.5, 'z': True}
], ids=['string', 'int', 'list', 'dict'])
def test_object_serializer_wrapper(serializer, value):
    binary = serializer.mimetype != 'application/json'
    wrapper = ObjectSerializerWrapper(serializer, binary)
    payload = wrapper.serialize(value)
    objects = wrapper.unserialize(payload)
    assert len(objects) == 1
    assert objects[0] == value


def test_wrap_serializer(serializer):
    wrapped = wrap_serializer(serializer)
    assert isinstance(wrapped, autobahn.Serializer)


def test_wrap_unsupported_serializer():
    exc = pytest.raises(TypeError, wrap_serializer, YAMLSerializer())
    exc.match('cannot adapt serializer of type text/yaml')
