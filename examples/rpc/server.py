"""This example demonstrates how to register a remote procedure handler with WAMP."""

from pathlib import Path
import logging

from asphalt.core import ContainerComponent, Context, run_application
from asphalt.wamp.utils import launch_crossbar


def uppercase(ctx, message: str):
    return message.upper()


class RPCServerComponent(ContainerComponent):
    async def start(self, ctx: Context):
        crossbar_dir = Path(__name__).parent / '.crossbar'
        launch_crossbar(crossbar_dir)

        self.add_component('wamp', url='ws://localhost:56666')
        await super().start(ctx)

        await ctx.wamp.register_procedure(uppercase, 'uppercase')

run_application(RPCServerComponent(), logging=logging.DEBUG)
