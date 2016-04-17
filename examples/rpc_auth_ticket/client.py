"""
This example demonstrates how to authenticate against the WAMP router with the "ticket" method.
It will make a call to the server that returns with a message containing the authentication ID
of this client.
"""

import asyncio
import logging

from asphalt.core import ContainerComponent, Context, run_application


class RPCClientComponent(ContainerComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:56666', auth_method='ticket',
                           auth_id='testclient', auth_secret='client123')
        await super().start(ctx)

        result = await ctx.wamp.call('hello')
        print('Server responded: {}'.format(result))

        asyncio.get_event_loop().stop()

run_application(RPCClientComponent(), logging=logging.DEBUG)
