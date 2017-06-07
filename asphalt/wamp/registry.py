import inspect
from collections import OrderedDict
from typing import Callable, Dict, Any, Union, NamedTuple, TypeVar

from autobahn.wamp.types import SubscribeOptions, RegisterOptions
from typeguard import check_argument_types

__all__ = ('Procedure', 'Subscriber', 'WAMPRegistry')

Procedure = NamedTuple('Procedure', [('name', str), ('handler', Callable),
                                     ('options', RegisterOptions)])
Subscriber = NamedTuple('Subscriber', [('topic', str), ('handler', Callable),
                                       ('options', SubscribeOptions)])
T_Options = TypeVar('T_Options')


def _validate_handler(handler: Callable, kind: str) -> None:
    spec = inspect.getfullargspec(handler)
    min_args = 2 if inspect.ismethod(handler) else 1
    if not spec.varargs and len(spec.args) < min_args:
        raise TypeError('{} must accept at least one positional argument'.format(kind))


def _apply_defaults(options: T_Options, defaults: T_Options) -> None:
    for attrname in dir(options.__class__):
        if not attrname.startswith('_'):
            value = getattr(options, attrname)
            if value is None:
                default = getattr(defaults, attrname)
                setattr(options, attrname, default)


class WAMPRegistry:
    """
    Hosts a collection of WAMP procedure and subscriber registrations and exception mappings.

    The purpose of this class is to ease the task of collecting all of the procedure handlers,
    event listeners and exception mappings of the application into a single place that the client
    can then use to register those on the router when a session has been opened.
    The alternative would be to call :meth:`~asphalt.wamp.client.WAMPClient.register_procedure`,
    :meth:`~asphalt.wamp.client.WAMPClient.subscribe` and
    :meth:`~asphalt.wamp.client.WAMPClient.map_exception` after
    :meth:`~asphalt.wamp.client.WAMPClient.connect`. This would not be very modular, however, since
    the code the connects the client would have to know about every single handler callbacks in
    advance.

    :ivar procedures: registered procedure handlers
    :vartype procedures: Dict[str, Procedure]
    :ivar subscriptions: registered event subscribers
    :vartype subscriptions: List[Subscription]
    :ivar exceptions: mapping of WAMP error code to exception class
    :vartype exceptions: Dict[str, type]
    """

    __slots__ = ('prefix', 'procedure_defaults', 'subscription_defaults', 'procedures',
                 'subscriptions', 'exceptions')

    def __init__(self, prefix: str = '', *,
                 procedure_defaults: Union[RegisterOptions, Dict[str, Any]] = None,
                 subscription_defaults: Union[SubscribeOptions, Dict[str, Any]] = None):
        """
        :param prefix: a prefix that is added to the name of every registered procedure
        :param procedure_defaults: default values to use for omitted arguments to
            :meth:`add_procedure`
        :param subscription_defaults: default values to use for omitted arguments to
            :meth:`add_subscriber`

        """
        assert check_argument_types()
        if prefix and not prefix.endswith('.'):
            prefix += '.'

        self.prefix = prefix
        if isinstance(procedure_defaults, dict):
            procedure_defaults = RegisterOptions(**procedure_defaults)
        elif procedure_defaults is None:
            procedure_defaults = RegisterOptions()

        if isinstance(subscription_defaults, dict):
            subscription_defaults = SubscribeOptions(**subscription_defaults)
        elif subscription_defaults is None:
            subscription_defaults = SubscribeOptions()

        self.procedure_defaults = procedure_defaults
        self.subscription_defaults = subscription_defaults
        self.procedures = OrderedDict()
        self.subscriptions = []
        self.exceptions = OrderedDict()

    def add_procedure(self, handler: Callable, name: str = None,
                      options: Union[RegisterOptions, Dict[str, Any]] = None) -> Procedure:
        """
        Add a procedure handler.

        The callable will receive a :class:`~asphalt.wamp.context.CallContext` instance as its
        first argument. The other positional and keyword arguments will be the arguments the caller
        passed to it.

        :param handler: callable that handles the procedure calls
        :param name: name of the endpoint to register (relative to registry's prefix); if ``None``,
            use the callable's internal name
        :param options: either an Autobahn register options object or a dictionary of keyword
            arguments to make one
        :return: the procedure registration object
        :raises TypeError: if the handler does not accept at least a single positional argument
        :raises ValueError: if there is already a handler registered for this endpoint

        .. seealso:: `How registrations work <http://crossbar.io/docs/How-Registrations-Work/>`_
        .. seealso:: `Pattern based registrations
            <http://crossbar.io/docs/Pattern-Based-Registrations/>`_
        .. seealso:: `Shared registrations <http://crossbar.io/docs/Shared-Registrations/>`_

        """
        assert check_argument_types()
        _validate_handler(handler, 'procedure handler')

        if isinstance(options, dict):
            options = RegisterOptions(**options)
        elif options is None:
            options = RegisterOptions()

        _apply_defaults(options, self.procedure_defaults)
        name = self.prefix + (name or handler.__name__)
        registration = Procedure(name, handler, options)
        if self.procedures.setdefault(name, registration) is not registration:
            raise ValueError('duplicate registration of procedure "{}"'.format(name))

        return registration

    def procedure(self, name: Union[str, Callable] = None,
                  options: Union[RegisterOptions, Dict[str, Any]] = None) -> Callable:
        """
        Decorator version of :meth:`add_procedure`.

        Can be used as ``@procedure(...)`` or simply ``@procedure``.

        If ``name`` has not been specified, the function name of the handler is used.

        :param name: name of the endpoint to register (relative to registry's prefix)
        :param options: either an Autobahn register options object or a dictionary of keyword
            arguments to make one

        """
        def wrapper(handler: Callable):
            self.add_procedure(handler, name, options)
            return handler

        if inspect.isfunction(name):
            handler, name = name, None
            return wrapper(handler)

        return wrapper

    def add_subscriber(self, handler: Callable, topic: str,
                       options: Union[SubscribeOptions, Dict[str, Any]] = None) -> Subscriber:
        """
        Decorator that registers a callable to receive events on the given topic.

        The callable  will receive an :class:`~asphalt.wamp.context.EventContext` instance as its
        first argument and must return an awaitable.
        The other positional and keyword arguments will be the arguments the publisher passed to
        the ``publish()`` method.

        The topic may contain wildcards (``a..b``).

        :param handler: callable that receives matching events
        :param topic: the topic to listen to
        :param options: either an Autobahn subscribe options object or a dictionary of keyword
            arguments to make one
        :return: the subscription registration object
        :raises TypeError: if the handler is not a coroutine or does not accept at least a single
            positional argument

        .. seealso:: `How subscriptions work <http://crossbar.io/docs/How-Subscriptions-Work/>`_
        .. seealso:: `Pattern based subscriptions
            <http://crossbar.io/docs/Pattern-Based-Subscriptions/>`_

        """
        assert check_argument_types()
        _validate_handler(handler, 'subscriber')

        if isinstance(options, dict):
            options = SubscribeOptions(**options)
        elif options is None:
            options = SubscribeOptions()

        _apply_defaults(options, self.subscription_defaults)
        topic = self.prefix + (topic or handler.__name__)
        subscription = Subscriber(topic, handler, options)
        self.subscriptions.append(subscription)
        return subscription

    def subscriber(self, topic: str,
                   options: Union[SubscribeOptions, Dict[str, Any]] = None) -> Callable:
        """
        Decorator version of :meth:`add_subscriber`.

        :param topic: the topic to listen to
        :param options: either an Autobahn subscribe options object or a dictionary of keyword
            arguments to make one

        .. seealso:: `How subscriptions work <http://crossbar.io/docs/How-Subscriptions-Work/>`_
        .. seealso:: `Pattern based subscriptions
            <http://crossbar.io/docs/Pattern-Based-Subscriptions/>`_

        """
        def wrapper(handler: Callable):
            self.add_subscriber(handler, topic, options)
            return handler

        return wrapper

    def map_exception(self, exc_type: type, code: str) -> None:
        """
        Map a Python exception class to a WAMP error code.

        :param code: the WAMP error code (e.g. ``foo.bar.baz``)
        :param exc_type: an exception class
        :raises TypeError: if ``exc_type`` does not inherit from :class`BaseException`

        """
        assert check_argument_types()
        if not isinstance(exc_type, type) or not issubclass(exc_type, BaseException):
            raise TypeError('exc_type must be a subclass of BaseException')

        self.exceptions[self.prefix + code] = exc_type

    def exception(self, error: str) -> Callable:
        """
        Decorator version of :meth:`map_exception`.

        :param error: the WAMP error code (e.g. ``foo.bar.baz``)

        """
        def wrapper(exc_class: type):
            self.map_exception(exc_class, error)
            return exc_class

        return wrapper

    def add_from(self, registry: 'WAMPRegistry', prefix: str = '') -> None:
        """
        Add all the procedures, subscribers and exception mappings from another registry to this
        one.

        If no prefix has been specified, the final name of each added procedure/subscriber endpoint
        or mapped error will be of the form ``<root prefix>.<name>``.
        If a prefix has been specified, the name will be ``<root prefix>.<prefix>.<name>``.

        :param registry: a WAMP registry
        :param prefix: prefix to add to names of all procedure endpoints

        """
        assert check_argument_types()
        if prefix and not prefix.endswith('.'):
            prefix += '.'

        for registration in registry.procedures.values():
            self.add_procedure(registration.handler, prefix + registration.name,
                               registration.options)

        for subscription in registry.subscriptions:
            self.add_subscriber(subscription.handler, prefix + subscription.topic,
                                subscription.options)

        for error, exc_type in registry.exceptions.items():
            self.map_exception(exc_type, prefix + error)

    def __repr__(self, *args, **kwargs):
        return '{}(prefix={!r})'.format(self.__class__.__name__, self.prefix)
