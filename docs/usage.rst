User guide
==========

The following sections explain how to use the most common functions of a WAMP client.
The more advanced options have been documented in the :ref:`API reference <modindex>`.

For practical examples, see the :github:`examples directory <examples>`.

Calling remote procedures
-------------------------

To call a remote procedure, use the :meth:`~asphalt.wamp.client.WAMPClient.call` method::

    result = await ctx.wamp.call('procedurename', arg1, arg2, arg3='foo')

To receive progressive results from the call, you can give a callback as the ``on_progress``
option::

    def progress(status):
        print('operation status: {}'.format(status))

    result = await ctx.wamp.call('procedurename', arg1, arg2, arg3='foo',
                                 options=dict(on_progress=progress))

To set a time limit for how long to wait for the call to complete, use the ``timeout`` option::

    # Wait 10 seconds until giving up
    result = await ctx.wamp.call('procedurename', arg1, arg2, arg3='foo', options=dict(timeout=10))

.. note:: This will **not** stop the remote handler from finishing; it will just make the client
    stop waiting and discard the results of the call.

Registering procedure handlers
------------------------------

To register a procedure on the router, create a callable that takes a
:class:`~asphalt.wamp.context.CallContext` as the first argument and use the
:meth:`~asphalt.wamp.client.WAMPClient.call` method to register it::

    async def procedure_handler(ctx: CallContext, *args, **kwargs):
        ...

    await ctx.wamp.register(procedure_handler, 'my_remote_procedure')

The handler can be either an asynchronous function or a regular function, but the latter will
obviously have fewer use cases due to the lack of ``await``.

To send progressive results, you can call the ``progress`` callback on the
:class:`~asphalt.wamp.context.CallContext` object. For this to work, the caller must have used the
``on_progress`` option when making the call. Otherwise ``progress`` will be ``None``.

For example::

    async def procedure_handler(ctx: CallContext, *args, **kwargs):
        for i in range(1, 11):
            await asyncio.sleep(1)
            if ctx.progress:
                ctx.progress('{}% complete'.format(i * 10))

        return 'Done'

    await ctx.wamp.register(procedure_handler, 'my_remote_procedure')

Publishing messages
-------------------

To publish a message on the router, call :meth:`~asphalt.wamp.client.WAMPClient.publish` with the
topic as the first argument and then add any positional and keyword arguments you want to include
in the message::

    await ctx.wamp.publish('some_topic', 'hello', 'world', another='argument')

By default, publications are not acknowledged by the router. This means that a published message
could be silently discarded if, for example, the publisher does not have proper permissions to
publish it. To avoid this, use the ``acknowledge`` option::

    await ctx.wamp.publish('some_topic', 'hello', 'world', another='argument',
                           options=dict(acknowledge=True))

Subscribing to topics
---------------------

You can use the :meth:`~asphalt.wamp.client.WAMPClient.subscribe` method to receive published
messages from the router::

    async def subscriber(ctx: EventContext, *args, **kwargs):
        print('new message: args={}, kwargs={}'.format(args, kwargs))

    await ctx.wamp.subscribe(subscriber, 'some_topic')

Just like procedure handlers, subscription handlers can be either an asynchronous or regular
functions.

Mapping WAMP exceptions to Python exceptions
--------------------------------------------

Exceptions transmitted over WAMP are identified by a specific URI. WAMP errors can be mapped to
Python exceptions by linking a specific URI to a specific exception class by means of either
:meth:`~asphalt.wamp.registry.WAMPRegistry.exception`,
:meth:`~asphalt.wamp.registry.WAMPRegistry.map_exception` or
:meth:`~asphalt.wamp.client.WAMPClient.map_exception`.

When you map an exception, you can raise it in your procedure or subscription handlers and it will
be automatically translated using the given error URI so that the recipients will be able to
properly map it on their end as well. Likewise, when a matching error is received from the router,
the appropriate exception class is instantiated and raised in the calling code.

Any unmapped exceptions manifest themselves as :class:`~autobahn.wamp.exception.ApplicationError`
exceptions.

Using registries to structure your application
----------------------------------------------

While it may at first seem convenient to register every procedure and subscription handler using
:meth:`~asphalt.wamp.client.WAMPClient.register` and
:meth:`~asphalt.wamp.client.WAMPClient.subscribe`, it does not scale very well when your
handlers are distributed over several packages and modules.

The :class:`~asphalt.wamp.registry.WAMPRegistry` class provides an alternative to this.
Each registry object stores registered procedure handlers, subscription handlers and mapped
exceptions, and can apply defaults on each of these. Each registry can have a separate namespace
prefix so you don't have to repeat it in every single procedure name, topic or mapped error.

Suppose you want to register two procedures and one subscriber, all under the ``foo`` prefix and
you want to apply the ``invoke='roundrobin'`` setting to all procedures::

    from asphalt.wamp import WAMPRegistry

    registry = WAMPRegistry('foo', procedure_defaults={'invoke': 'roundrobin'})


    @registry.procedure
    def multiply(ctx, factor1, factor2):
        return factor1 * factor2


    @registry.procedure
    def divide(ctx, numerator, denominator):
        return numerator / denominator


    @registry.subscriber
    def message_received(ctx, message):
        print('new message: %s' % message)

To use the registry, pass it to the WAMP component as an option::

    class ApplicationComponent(ContainerComponent):
        async def start(ctx):
            ctx.add_component('wamp', registry=registry)
            await super.start(ctx)

This will register the ``foo.multiply``, ``foo.divide`` procedures and a subscriptions for the
``foo.message_received`` topic.

Say your procedures and/or subscribers are spread over several modules and you want a different
namespace for every module, you could have a separate registry in every module and then combine
them into a single registry using :meth:`~asphalt.wamp.registry.WAMPRegistry.add_from`::

    from asphalt.wamp import WAMPRegistry

    from myapp.services import accounting, deliveries, production  # these are modules

    registry = WAMPRegistry()
    registry.add_from(accounting.registry, 'accounting')
    registry.add_from(deliveries.registry, 'deliveries')
    registry.add_from(production.registry, 'production')

You can set the prefix either in the call to :meth:`~asphalt.wamp.registry.WAMPRegistry.add_from`
or when creating the registry of each subsection. Note that if you do both, you end up with two
prefixes!
