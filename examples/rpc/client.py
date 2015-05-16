"""This example demonstrates how to make RPC calls with WAMP."""

from asyncio import coroutine
import logging
import sys

from asphalt.core.component import ContainerComponent
from asphalt.core.concurrency import stop_event_loop
from asphalt.core.context import Context
from asphalt.core.runner import run_application


class RPCClientComponent(ContainerComponent):
    @coroutine
    def start(self, ctx: Context):
        port, message = sys.argv[1:]
        self.add_component('wamp', url='ws://localhost:{}'.format(port))
        yield from super().start(ctx)

        result = yield from ctx.wamp.call('uppercase', message)
        print('{!r} translated to upper case is {!r}'.format(message, result))

        stop_event_loop()

if len(sys.argv) < 3:
    print('Usage: {} <port> <text>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(RPCClientComponent(), logging=logging.DEBUG)
