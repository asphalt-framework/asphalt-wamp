"""
This example demonstrates how to authenticate against the WAMP router with the "wampcra" method.
It will make a call to the server that returns with a message containing the authentication ID
of this client.
"""

import logging

from asphalt.core import CLIApplicationComponent, Context, run_application

logger = logging.getLogger(__name__)


class RPCClientComponent(CLIApplicationComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', auth_method='wampcra',
                           auth_id='testclient', auth_secret='client123')
        await super().start(ctx)

    async def run(self, ctx: Context):
        result = await ctx.wamp.call('hello')
        logger.info('Server responded: %s', result)


run_application(RPCClientComponent(), logging=logging.INFO)
