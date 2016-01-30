"""
This example demonstrates how to publish messages with WAMP.

First start subscriber.py and take note of which port it's running on.
You will need to give this port number as the first argument to this script.
"""

from asyncio import coroutine
import logging
import sys

from asphalt.core.component import ContainerComponent
from asphalt.core.concurrency import stop_event_loop
from asphalt.core.context import Context
from asphalt.core.runner import run_application

logger = logging.getLogger(__name__)


class PublisherComponent(ContainerComponent):
    @coroutine
    def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:56666')
        yield from super().start(ctx)

        port, topic, message = sys.argv[1:]
        yield from ctx.wamp.publish(topic, message)

        stop_event_loop()

if len(sys.argv) < 3:
    print('Usage: {} <topic> <message>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(PublisherComponent(), logging=logging.DEBUG)
