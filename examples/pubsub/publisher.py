"""
This example demonstrates how to publish messages with WAMP.

First start subscriber.py and take note of which port it's running on.
"""

import asyncio
import logging
import sys

from asphalt.core import ContainerComponent, Context, run_application

logger = logging.getLogger(__name__)


class PublisherComponent(ContainerComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:8080')
        await super().start(ctx)

        topic, message = sys.argv[1:3]
        await ctx.wamp.publish(topic, message)
        asyncio.get_event_loop().stop()

if len(sys.argv) < 3:
    print('Usage: {} <topic> <message>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(PublisherComponent(), logging=logging.INFO)
