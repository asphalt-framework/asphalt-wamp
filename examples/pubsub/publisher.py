"""This example demonstrates how to publish messages with WAMP."""

import logging
import sys

from asphalt.core import CLIApplicationComponent, Context, run_application

logger = logging.getLogger(__name__)


class PublisherComponent(CLIApplicationComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp')
        await super().start(ctx)

    async def run(self, ctx: Context):
        topic, message = sys.argv[1:3]
        await ctx.wamp.publish(topic, message)


if len(sys.argv) < 3:
    print('Usage: {} <topic> <message>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(PublisherComponent(), logging=logging.INFO)
