"""
This example WAMP client first calls the ``test.reverse`` remote method with string given as the
command line. It then publishes the return value on the ``topics.subtopic`` topic.
"""

import logging
import sys

from asphalt.core import CLIApplicationComponent, Context, run_application


class RPCClientComponent(CLIApplicationComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp')
        await super().start(ctx)

    async def run(self, ctx: Context):
        message = sys.argv[1]
        result = await ctx.wamp.call('test.reverse', message)
        await ctx.wamp.publish('topics.subtopic', result)


if len(sys.argv) < 2:
    print('Usage: {} <text>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(RPCClientComponent(), logging=logging.INFO)
