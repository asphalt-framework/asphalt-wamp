from asphalt.serialization.api import Serializer
from autobahn.wamp import serializer as autobahn
from autobahn.wamp.interfaces import IObjectSerializer


class ObjectSerializerWrapper(IObjectSerializer):
    def __init__(self, serializer: Serializer, binary: bool):
        self._serializer = serializer
        self._binary = binary

    @property
    def BINARY(self) -> bool:
        return self._binary

    def serialize(self, obj) -> bytes:
        return self._serializer.serialize(obj)

    def unserialize(self, payload: bytes):
        return [self._serializer.deserialize(payload)]


class SerializerWrapper(autobahn.Serializer):
    def __init__(self, serializer: Serializer, serializer_id: str, rawsocket_id: int,
                 binary: bool):
        super(SerializerWrapper, self).__init__(ObjectSerializerWrapper(serializer, binary))
        self.SERIALIZER_ID = serializer_id
        self.RAWSOCKET_SERIALIZER_ID = rawsocket_id
        self.MIME_TYPE = serializer.mimetype


def wrap_serializer(serializer: Serializer):
    if serializer.mimetype == 'application/json':
        return SerializerWrapper(serializer, 'json', 1, False)
    elif serializer.mimetype == 'application/msgpack':
        return SerializerWrapper(serializer, 'msgpack', 2, True)
    elif serializer.mimetype == 'application/cbor':
        return SerializerWrapper(serializer, 'cbor', 3, True)

    raise TypeError('cannot adapt serializer of type {}'.format(serializer.mimetype))
