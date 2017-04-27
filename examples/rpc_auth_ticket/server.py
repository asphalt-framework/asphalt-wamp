"""
This example demonstrates how to find out the caller's authentication ID (username).
It should be noted that for this to work with Crossbar at least, caller disclosure must be enabled
in the authentication configuration.
"""

import logging

from asphalt.core import ContainerComponent, Context, run_application
from asphalt.wamp.context import CallContext


def hello(ctx: CallContext):
    return 'Hello, {}!'.format(ctx.caller_auth_id)


class RPCServerComponent(ContainerComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', auth_method='ticket',
                           auth_id='testserver', auth_secret='server123')
        await super().start(ctx)

        await ctx.wamp.register(hello, 'hello')


run_application(RPCServerComponent(), logging=logging.INFO)
