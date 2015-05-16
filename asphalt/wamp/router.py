from collections import OrderedDict
from functools import partial
from typing import Callable

from .utils import validate_handler


class WAMPRouter:
    """
    This class is not an actual router, but rather something that collects WAMP procedure endpoints
    and event subscribers for registration with an actual WAMP router.

    :param prefix: a prefix that is added to the name of every registered procedure
    :ivar Dict[str, Callable] procedures: registered procedure handlers
    :ivar List[Tuple[str, Callable]] subscriptions: registered event subscribers
    :ivar Dict[str, type] exceptions: WAMP error to exception class mappings
    """

    def __init__(self, prefix: str=None):
        self.prefix = (prefix + '.') if prefix else ''
        self.procedures = OrderedDict()
        self.subscriptions = []
        self.exceptions = OrderedDict()

    def procedure(self, handler: Callable=None, *, name: str=None):
        """
        Decorator that register a callable to handle incoming procedure calls on a endpoint.

        The callable must be a coroutine. It will receive a
        :class:`~asphalt.wamp.context.CallContext` instance as its first argument.
        The other positional and keyword arguments will be the arguments the caller passed to
        the ``call()`` method.

        If ``name`` has not been specified, the name of the handler is used.

        :param handler: callable that handles the procedure calls
        :param name: name of the endpoint to register (relative to router's prefix)
        :raises TypeError: if the handler is not a coroutine or does not accept at least a single
            positional argument
        :raises ValueError: if there is already a handler registered for this endpoint

        """
        if handler is None:
            return partial(self.procedure, name=name)

        unwrapped_handler = validate_handler(handler, 'procedure handler')
        name = name or unwrapped_handler.__name__
        name = self.prefix + name
        if name in self.procedures:
            raise ValueError('duplicate registration of procedure "{}"'.format(name))

        self.procedures[name] = handler
        return handler

    def subscriber(self, topic: str):
        """
        Decorator that registers a callable to receive events on the given topic.

        The callable must be a coroutine. It will receive an
        :class:`~asphalt.wamp.context.EventContext` instance as its first argument.
        The other positional and keyword arguments will be the arguments the publisher passed to
        the ``publish()`` method.

        The topic may contain wildcards (``a.b.*``).

        :param topic: the topic to listen to
        :raises TypeError: if the handler is not a coroutine or does not accept at least a single
            positional argument

        """
        def wrapper(handler: Callable):
            validate_handler(handler, 'subscriber')
            self.subscriptions.append((topic, handler))
            return handler

        return wrapper

    def exception(self, error: str, exc_type: type=None):
        """
        Map a Python exception to a WAMP exception.

        This method is usable either as a decorator (one argument) or directly (two arguments).

        :param error: the WAMP error code (e.g. ``foo.bar.baz``)
        :param exc_type: an exception class
        :raises TypeError: if ``exc_type`` does not inherit from :class`BaseException`

        """
        if exc_type is None:
            return partial(self.exception, error)

        if not isinstance(exc_type, type) or not issubclass(exc_type, BaseException):
            raise TypeError('exc_type must be a subclass of BaseException')

        self.exceptions[error] = exc_type

    def attach(self, router: 'WAMPRouter', prefix: str=None):
        """
        Add all the procedures, subscribers and exception mappings from another router to this one.

        If no prefix has been specified, the final name of each added procedure endpoint will be
        of the form ``<root prefix>.<attached procedure name>``.
        If a prefix has been specified, the name will be
        ``<root prefix>.<prefix>.<attached procedure name>``.

        Event subscriptions and exception mappings are unaffected by prefixes.

        :param router: a WAMP router
        :param prefix: prefix to add to names of all procedure endpoints

        """
        prefix = (prefix + '.') if prefix else ''
        for name, handler in router.procedures.items():
            self.procedure(handler, name=prefix + name)

        for topic, handler in router.subscriptions:
            self.subscriber(topic)(handler)

        for error, exc_type in router.exceptions.items():
            self.exception(error, exc_type)
