"""This example demonstrates how to register a remote procedure handler with WAMP."""

from asyncio import coroutine
import logging

from asphalt.core.component import ContainerComponent
from asphalt.core.context import Context
from asphalt.core.runner import run_application
from asphalt.wamp.utils import launch_crossbar


@coroutine
def uppercase(ctx, message: str):
    return message.upper()


class RPCServerComponent(ContainerComponent):
    @coroutine
    def start(self, ctx: Context):
        port = launch_crossbar()
        url = 'ws://localhost:{}'.format(port)
        self.add_component('wamp', url=url)
        yield from super().start(ctx)

        # Register the procedure handler as "uppercase"
        yield from ctx.wamp.register(uppercase, 'uppercase')

run_application(RPCServerComponent(), logging=logging.DEBUG)
