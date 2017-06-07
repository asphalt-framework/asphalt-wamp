import pytest
from autobahn.wamp.types import RegisterOptions, SubscribeOptions

from asphalt.wamp.registry import WAMPRegistry


@pytest.fixture
def registry():
    return WAMPRegistry(procedure_defaults=RegisterOptions(concurrency=1),
                        subscription_defaults=SubscribeOptions(get_retained=True))


async def dummyhandler(ctx):
    pass


def test_defaults_as_dicts():
    registry = WAMPRegistry(procedure_defaults=dict(concurrency=1),
                            subscription_defaults=dict(get_retained=True))
    assert registry.procedure_defaults.concurrency == 1
    assert registry.subscription_defaults.get_retained


@pytest.mark.parametrize('use_dict', [False, True])
@pytest.mark.parametrize('use_decorator', [False, True])
def test_procedure(registry: WAMPRegistry, use_dict, use_decorator):
    options = dict(match='prefix', invoke='roundrobin')
    if not use_dict:
        options = RegisterOptions(**options)

    if use_decorator:
        registry.procedure('procedurename', options)(dummyhandler)
    else:
        registry.add_procedure(dummyhandler, 'procedurename', options)

    assert list(registry.procedures.keys()) == ['procedurename']
    procedure = registry.procedures['procedurename']
    assert procedure.handler is dummyhandler
    assert procedure.name == 'procedurename'
    assert procedure.options.concurrency == 1


def test_procedure_bad_argument_count(registry: WAMPRegistry):
    def invalid_procedure_handler():
        pass

    exc = pytest.raises(TypeError, registry.add_procedure, invalid_procedure_handler, 'procedure')
    exc.match('procedure handler must accept at least one positional argument')


def test_procedure_simple_decorator(registry: WAMPRegistry):
    registry.procedure(dummyhandler)
    assert list(registry.procedures.keys()) == ['dummyhandler']
    assert registry.procedures['dummyhandler'].handler is dummyhandler


def test_duplicate_procedure(registry: WAMPRegistry):
    registry.add_procedure(dummyhandler, 'handler')

    exc = pytest.raises(ValueError, registry.add_procedure, dummyhandler, 'handler')
    exc.match('duplicate registration of procedure "handler"')


@pytest.mark.parametrize('use_dict', [False, True])
@pytest.mark.parametrize('use_decorator', [False, True])
def test_subscriber(registry: WAMPRegistry, use_dict, use_decorator):
    options = dict(match='prefix')
    if not use_dict:
        options = SubscribeOptions(**options)

    if use_decorator:
        registry.subscriber('topic', options)(dummyhandler)
    else:
        registry.add_subscriber(dummyhandler, 'topic', options)

    assert len(registry.subscriptions) == 1
    subscription = registry.subscriptions[0]
    assert subscription.handler is dummyhandler
    assert subscription.topic == 'topic'
    assert subscription.options.match == 'prefix'
    assert subscription.options.get_retained


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
    child_registry = WAMPRegistry('child', procedure_defaults=RegisterOptions(invoke='roundrobin'),
                                  subscription_defaults=SubscribeOptions(match='prefix'))
    child_registry.add_procedure(dummyhandler, 'procedure', RegisterOptions(match='exact'))
    child_registry.add_subscriber(dummyhandler, 'topic', SubscribeOptions(match='exact'))
    child_registry.map_exception(RuntimeError, 'x.y.z')

    parent_registry = WAMPRegistry(
        'parent', procedure_defaults=RegisterOptions(match='prefix', invoke='first',
                                                     concurrency=2),
        subscription_defaults=SubscribeOptions(match='wildcard', get_retained=True)
    )
    parent_registry.add_from(child_registry, prefix)

    procedure_name = 'parent.{}child.procedure'.format((prefix + '.') if prefix else '')
    assert len(parent_registry.procedures) == 1
    assert parent_registry.procedures[procedure_name].options.match == 'exact'
    assert parent_registry.procedures[procedure_name].options.invoke == 'roundrobin'
    assert parent_registry.procedures[procedure_name].options.concurrency == 2

    expected_topic = 'parent.{}child.topic'.format((prefix + '.') if prefix else '')
    assert len(parent_registry.subscriptions) == 1
    assert parent_registry.subscriptions[0].topic == expected_topic
    assert parent_registry.subscriptions[0].options.match == 'exact'

    exception_name = 'parent.{}child.x.y.z'.format((prefix + '.') if prefix else '')
    assert parent_registry.exceptions == {exception_name: RuntimeError}


def test_repr(registry: WAMPRegistry):
    assert repr(registry) == "WAMPRegistry(prefix='')"
