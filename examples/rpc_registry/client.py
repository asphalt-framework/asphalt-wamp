"""
This example WAMP client first calls the ``test.reverse`` remote method with string given as the
command line. It then publishes the return value on the ``topic.subtopic`` topic.
"""

import asyncio
import logging
import sys

from asphalt.core import ContainerComponent, Context, run_application


class RPCClientComponent(ContainerComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:56666')
        await super().start(ctx)

        message = sys.argv[1]
        result = await ctx.wamp.call('test.reverse', message)
        await ctx.wamp.publish('topic.subtopic', result)

        asyncio.get_event_loop().stop()

if len(sys.argv) < 2:
    print('Usage: {} <text>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(RPCClientComponent(), logging=logging.DEBUG)
