"""This example demonstrates how to make RPC calls with WAMP."""

import logging
import sys

from asphalt.core import CLIApplicationComponent, Context, run_application

logger = logging.getLogger(__name__)


class RPCClientComponent(CLIApplicationComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp')
        await super().start(ctx)

    async def run(self, ctx: Context):
        message = sys.argv[1]
        result = await ctx.wamp.call('uppercase', message)
        logger.info('%r translated to upper case is %r', message, result)


if len(sys.argv) < 2:
    print('Usage: {} <text>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(RPCClientComponent(), logging=logging.INFO)
