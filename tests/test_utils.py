from asyncio import coroutine

import pytest

from asphalt.wamp.utils import validate_handler


class Dummy:
    @classmethod
    def classmethod_handler1(cls, ctx):
        pass

    @classmethod
    def classmethod_handler2(cls, *args):
        pass

    @classmethod
    def classmethod_handler3(cls):
        pass


@pytest.mark.parametrize('handler', [
    lambda ctx: None,
    lambda *args: None,
    Dummy.classmethod_handler1,
    Dummy.classmethod_handler2
], ids=['func_1arg', 'func_varargs', 'classmethod_1arg', 'classmethod_varargs'])
def test_validate_handler(handler):
    validate_handler(coroutine(handler), 'xyz')


@pytest.mark.parametrize('handler', [
    lambda: None,
    Dummy.classmethod_handler3
], ids=['func', 'classmethod'])
def test_validate_handler_insufficient_args(handler):
    exc = pytest.raises(TypeError, validate_handler, coroutine(handler), 'xyz')
    assert str(exc.value) == 'xyz must accept at least one positional argument'
