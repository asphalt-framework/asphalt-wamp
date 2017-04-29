import pytest

from asphalt.wamp.registry import WAMPRegistry, Subscriber, Procedure


@pytest.fixture
def registry():
    return WAMPRegistry()


async def dummyhandler(ctx):
    pass


@pytest.mark.parametrize('use_decorator', [False, True])
def test_procedure(registry: WAMPRegistry, use_decorator):
    options = {'match': 'prefix', 'invoke': 'roundrobin'}
    if use_decorator:
        registry.procedure(name='procedurename', **options)(dummyhandler)
    else:
        registry.add_procedure(dummyhandler, 'procedurename', **options)

    expected = Procedure('procedurename', dummyhandler, options)
    assert registry.procedures == {'procedurename': expected}


def test_procedure_bad_argument_count(registry: WAMPRegistry):
    def invalid_procedure_handler():
        pass

    exc = pytest.raises(TypeError, registry.add_procedure, invalid_procedure_handler, 'procedure')
    exc.match('procedure handler must accept at least one positional argument')


def test_procedure_simple_decorator(registry: WAMPRegistry):
    registry.procedure(dummyhandler)
    expected = Procedure('dummyhandler', dummyhandler, registry.procedure_defaults)
    assert registry.procedures == {'dummyhandler': expected}


def test_duplicate_procedure(registry: WAMPRegistry):
    registry.add_procedure(dummyhandler, 'handler')

    exc = pytest.raises(ValueError, registry.add_procedure, dummyhandler, 'handler')
    exc.match('duplicate registration of procedure "handler"')


@pytest.mark.parametrize('use_decorator', [False, True])
def test_subscriber(registry: WAMPRegistry, use_decorator):
    options = {'match': 'prefix'}
    if use_decorator:
        registry.subscriber('topic', **options)(dummyhandler)
    else:
        registry.add_subscriber(dummyhandler, 'topic', **options)

    assert registry.subscriptions == [Subscriber('topic', dummyhandler, options)]


def test_subscriber_argument_count(registry: WAMPRegistry):
    def invalid_subscriber():
        pass

    exc = pytest.raises(TypeError, registry.add_subscriber, invalid_subscriber, 'topic')
    exc.match('subscriber must accept at least one positional argument')


@pytest.mark.parametrize('use_decorator', [False, True])
def test_exception_decorator(registry: WAMPRegistry, use_decorator):
    if use_decorator:
        registry.exception('x.y.z')(RuntimeError)
    else:
        registry.map_exception(RuntimeError, 'x.y.z')

    assert registry.exceptions == {'x.y.z': RuntimeError}


def test_invalid_exception(registry: WAMPRegistry):
    exc = pytest.raises(TypeError, registry.map_exception, str, 'x.y.z')
    exc.match('exc_type must be a subclass of BaseException')


@pytest.mark.parametrize('prefix', ['', 'middle'])
def test_add_from(prefix):
    child_registry = WAMPRegistry('child')
    child_registry.add_procedure(dummyhandler, 'procedure')
    child_registry.add_subscriber(dummyhandler, 'topic')
    child_registry.map_exception(RuntimeError, 'x.y.z')

    parent_registry = WAMPRegistry('parent')
    parent_registry.add_from(child_registry, prefix)
    procedure_name = 'parent.{}child.procedure'.format((prefix + '.') if prefix else '')
    assert parent_registry.procedures == {
        procedure_name: Procedure(procedure_name, dummyhandler, parent_registry.procedure_defaults)
    }
    assert parent_registry.subscriptions == [
        Subscriber('parent.child.topic', dummyhandler, {'match': 'exact'})]
    assert parent_registry.exceptions == {'x.y.z': RuntimeError}


def test_repr(registry: WAMPRegistry):
    assert repr(registry) == "WAMPRegistry(prefix='')"
