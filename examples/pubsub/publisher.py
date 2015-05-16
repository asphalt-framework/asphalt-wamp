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
        port, topic, message = sys.argv[1:]
        self.add_component('wamp', url='ws://localhost:{}'.format(port))
        yield from super().start(ctx)
        yield from ctx.wamp.publish(topic, message)
        logger.info('Published "%s" to topic "%s"', message, topic)
        stop_event_loop()

if len(sys.argv) < 4:
    print('Usage: {} <port> <topic> <message>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(PublisherComponent(), logging=logging.DEBUG)
