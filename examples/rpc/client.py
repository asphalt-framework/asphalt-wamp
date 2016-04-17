"""This example demonstrates how to make RPC calls with WAMP."""

import asyncio
import logging
import sys

from asphalt.core import ContainerComponent, Context, run_application


class RPCClientComponent(ContainerComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:56666')
        await super().start(ctx)

        message = sys.argv[1]
        result = await ctx.wamp.call('uppercase', message)
        print('{!r} translated to upper case is {!r}'.format(message, result))

        asyncio.get_event_loop().stop()


if len(sys.argv) < 2:
    print('Usage: {} <text>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(RPCClientComponent(), logging=logging.DEBUG)
