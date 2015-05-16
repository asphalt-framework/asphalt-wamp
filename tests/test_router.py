from asyncio import coroutine

import pytest

from asphalt.wamp.router import WAMPRouter


def test_procedure_decorator():
    @coroutine
    def dummyhandler(ctx):
        pass

    router = WAMPRouter()
    router.procedure(name='procedurename')(dummyhandler)
    assert router.procedures == {'procedurename': dummyhandler}


def test_exception_decorator():
    router = WAMPRouter()
    router.exception('x.y.z')(RuntimeError)
    assert router.exceptions == {'x.y.z': RuntimeError}


def test_duplicate_procedure():
    handler1 = coroutine(lambda ctx: None)
    handler2 = coroutine(lambda ctx: None)
    router = WAMPRouter()
    router.procedure(handler1, name='handler')
    exc = pytest.raises(ValueError, router.procedure, handler2, name='handler')
    assert str(exc.value) == 'duplicate registration of procedure "handler"'


def test_invalid_exception():
    router = WAMPRouter()
    exc = pytest.raises(TypeError, router.exception, 'x.y.z', str)
    assert str(exc.value) == 'exc_type must be a subclass of BaseException'


@pytest.mark.parametrize('prefix', [None, 'middle'])
def test_attach(prefix):
    handler = coroutine(lambda ctx: None)
    child_router = WAMPRouter('child')
    child_router.procedure(handler, name='procedure')
    child_router.subscriber('topic')(handler)
    child_router.exception('x.y.z', RuntimeError)

    parent_router = WAMPRouter('parent')
    parent_router.attach(child_router, prefix)
    procedure_name = 'parent.{}child.procedure'.format((prefix + '.') if prefix else '')
    assert parent_router.procedures == {procedure_name: handler}
    assert parent_router.subscriptions == [('topic', handler)]
    assert parent_router.exceptions == {'x.y.z': RuntimeError}
