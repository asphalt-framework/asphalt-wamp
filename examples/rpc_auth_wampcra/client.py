"""
This example demonstrates how to authenticate against the WAMP router with the "wampcra" method.
It will make a call to the server that returns with a message containing the authentication ID
of this client.
"""

import asyncio
import logging

from asphalt.core import ContainerComponent, Context, run_application

logger = logging.getLogger(__name__)


class RPCClientComponent(ContainerComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:8080', auth_method='wampcra',
                           auth_id='testclient', auth_secret='client123')
        await super().start(ctx)

        result = await ctx.wamp.call('hello')
        logger.info('Server responded: %s', result)
        asyncio.get_event_loop().stop()

run_application(RPCClientComponent(), logging=logging.INFO)
