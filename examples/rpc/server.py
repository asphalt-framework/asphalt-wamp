"""This example demonstrates how to register a remote procedure handler with WAMP."""

from asyncio import coroutine
from pathlib import Path
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
        crossbar_dir = Path(__name__).parent / '.crossbar'
        launch_crossbar(crossbar_dir)

        self.add_component('wamp', url='ws://localhost:56666')
        yield from super().start(ctx)

        yield from ctx.wamp.register_procedure(uppercase, 'uppercase')

run_application(RPCServerComponent(), logging=logging.DEBUG)
