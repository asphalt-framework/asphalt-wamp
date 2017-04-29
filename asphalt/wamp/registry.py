import inspect
from collections import OrderedDict, Awaitable
from typing import Callable, Dict, Any, Union, NamedTuple

from typeguard import check_argument_types

__all__ = ('Procedure', 'Subscriber', 'WAMPRegistry')

Procedure = NamedTuple('Procedure', [('name', str), ('handler', Callable),
                                     ('options', Dict[str, Any])])
Subscriber = NamedTuple('Subscriber', [('topic', str), ('handler', Callable),
                                       ('options', Dict[str, Any])])


def _validate_handler(handler: Callable, kind: str) -> None:
    spec = inspect.getfullargspec(handler)
    min_args = 2 if inspect.ismethod(handler) else 1
    if not spec.varargs and len(spec.args) < min_args:
        raise TypeError('{} must accept at least one positional argument'.format(kind))


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

    Procedures have the following default registration options:

    * match: ``exact``
    * invoke: ``single``

    Event subscribers have the following default registration options:

    * match: ``exact``

    :ivar procedures: registered procedure handlers
    :vartype procedures: Dict[str, ProcedureRegistration]
    :ivar subscriptions: registered event subscribers
    :vartype subscriptions: List[Subscription]
    :ivar exceptions: mapping of WAMP error code to exception class
    :vartype exceptions: Dict[str, type]
    """

    __slots__ = ('prefix', 'procedure_defaults', 'subscription_defaults', 'procedures',
                 'subscriptions', 'exceptions')

    def __init__(self, prefix: str = '', *, procedure_defaults: Dict[str, Any] = None,
                 subscription_defaults: Dict[str, Any] = None):
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
        self.procedure_defaults = procedure_defaults or {}
        self.procedure_defaults.setdefault('match', 'exact')
        self.procedure_defaults.setdefault('invoke', 'single')
        self.subscription_defaults = subscription_defaults or {}
        self.subscription_defaults.setdefault('match', 'exact')

        self.procedures = OrderedDict()
        self.subscriptions = []
        self.exceptions = OrderedDict()

    def add_procedure(self, handler: Callable, name: str = None, *, match: str = None,
                      invoke: str = None) -> Procedure:
        """
        Add a procedure handler.

        The callable will receive a :class:`~asphalt.wamp.context.CallContext` instance as its
        first argument. The other positional and keyword arguments will be the arguments the caller
        passed to it.

        :param handler: callable that handles the procedure calls
        :param name: name of the endpoint to register (relative to registry's prefix); if ``None``,
            use the callable's internal name
        :param match: one of ``exact``, ``prefix``, ``wildcard``
        :param invoke: one of ``single``, ``roundrobin``, ``random``, ``first``, ``last``
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
        options = {'match': match or self.procedure_defaults['match'],
                   'invoke': invoke or self.procedure_defaults['invoke']}
        name = self.prefix + (name or handler.__name__)
        registration = Procedure(name, handler, options)
        if self.procedures.setdefault(name, registration) is not registration:
            raise ValueError('duplicate registration of procedure "{}"'.format(name))

        return registration

    def procedure(self, name: Union[str, Callable] = None, *, match: str = None,
                  invoke: str = None) -> Callable:
        """
        Decorator version of :meth:`add_procedure`.

        Can be used as ``@procedure(...)`` or simply ``@procedure``.

        If ``name`` has not been specified, the function name of the handler is used.

        :param name: name of the endpoint to register (relative to registry's prefix)
        :param match: one of ``exact``, ``prefix``, ``wildcard``
        :param invoke: one of ``single``, ``roundrobin``, ``random``, ``first``, ``last``

        """
        def wrapper(handler: Callable):
            self.add_procedure(handler, name, match=match, invoke=invoke)
            return handler

        if inspect.isfunction(name):
            handler, name = name, None
            return wrapper(handler)

        return wrapper

    def add_subscriber(self, handler: Callable[..., Awaitable], topic: str, *,
                       match: str = None) -> Subscriber:
        """
        Decorator that registers a callable to receive events on the given topic.

        The callable  will receive an :class:`~asphalt.wamp.context.EventContext` instance as its
        first argument and must return an awaitable.
        The other positional and keyword arguments will be the arguments the publisher passed to
        the ``publish()`` method.

        The topic may contain wildcards (``a..b``).

        :param handler: callable that receives matching events
        :param topic: the topic to listen to
        :param match: one of ``exact``, ``prefix`` or ``wildcard`` (omit for the default value)
        :return: the subscription registration object
        :raises TypeError: if the handler is not a coroutine or does not accept at least a single
            positional argument

        .. seealso:: `How subscriptions work <http://crossbar.io/docs/How-Subscriptions-Work/>`_
        .. seealso:: `Pattern based subscriptions
            <http://crossbar.io/docs/Pattern-Based-Subscriptions/>`_

        """
        assert check_argument_types()
        _validate_handler(handler, 'subscriber')
        options = {'match': match or self.subscription_defaults['match']}
        topic = self.prefix + (topic or handler.__name__)
        subscription = Subscriber(topic, handler, options)
        self.subscriptions.append(subscription)
        return subscription

    def subscriber(self, topic: str, *, match: str = None) -> Callable:
        """
        Decorator version of :meth:`add_subscriber`.

        :param topic: the topic to listen to
        :param match: one of ``exact``, ``prefix`` or ``wildcard``

        .. seealso:: `How subscriptions work <http://crossbar.io/docs/How-Subscriptions-Work/>`_
        .. seealso:: `Pattern based subscriptions
            <http://crossbar.io/docs/Pattern-Based-Subscriptions/>`_

        """
        def wrapper(handler: Callable):
            self.add_subscriber(handler, topic, match=match)
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

        self.exceptions[code] = exc_type

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

        If no prefix has been specified, the final name of each added procedure endpoint will be
        of the form ``<root prefix>.<attached procedure name>``.
        If a prefix has been specified, the name will be
        ``<root prefix>.<prefix>.<attached procedure name>``.

        If a prefix is present in both the given registry and the ``prefix`` argument to this
        method, the ``prefix`` argument value is preferred.

        Prefixes only apply to procedure registrations; event subscriptions and exception mappings
        are unaffected.

        :param registry: a WAMP registry
        :param prefix: prefix to add to names of all procedure endpoints

        """
        assert check_argument_types()
        if prefix and not prefix.endswith('.'):
            prefix += '.'

        for registration in registry.procedures.values():
            self.add_procedure(registration.handler, prefix + registration.name,
                               **registration.options)

        for registration in registry.subscriptions:
            self.add_subscriber(registration.handler, registration.topic, **registration.options)

        for error, exc_type in registry.exceptions.items():
            self.map_exception(exc_type, error)

    def __repr__(self, *args, **kwargs):
        return '{}(prefix={!r})'.format(self.__class__.__name__, self.prefix)
