"""This example demonstrates how to find out the caller's authentication ID (username)."""

from pathlib import Path
import logging

from asphalt.core import ContainerComponent, Context, run_application
from asphalt.wamp.context import CallContext
from asphalt.wamp.utils import launch_crossbar


def hello(ctx: CallContext):
    return 'Hello, {}!'.format(ctx.caller_auth_id)


class RPCServerComponent(ContainerComponent):
    async def start(self, ctx: Context):
        crossbar_dir = Path(__name__).parent / '.crossbar'
        launch_crossbar(crossbar_dir)

        self.add_component('wamp', url='ws://localhost:56666', auth_method='ticket',
                           auth_id='testserver', auth_secret='server123')
        await super().start(ctx)

        await ctx.wamp.register_procedure(hello, 'hello')

run_application(RPCServerComponent(), logging=logging.DEBUG)
