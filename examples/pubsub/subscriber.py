"""
This example demonstrates how to subscribe to topics with WAMP.

First start subscriber.py and take note of which port it's running on.
You will need to give this port number as the first argument to this script.
"""

from asyncio import coroutine
from pathlib import Path
import logging
import sys

from asphalt.core.component import ContainerComponent
from asphalt.core.context import Context
from asphalt.core.runner import run_application
from asphalt.wamp.context import EventContext
from asphalt.wamp.utils import launch_crossbar

logger = logging.getLogger(__name__)


@coroutine
def subscriber(ctx: EventContext, message: str):
    logger.info('Received message from %s: %s', ctx.topic, message)


class PublisherComponent(ContainerComponent):
    @coroutine
    def start(self, ctx: Context):
        crossbar_dir = Path(__name__).parent / '.crossbar'
        launch_crossbar(crossbar_dir)

        self.add_component('wamp', url='ws://localhost:56666')
        yield from super().start(ctx)

        topic = sys.argv[1]
        yield from ctx.wamp.subscribe(subscriber, topic)
        logger.info('Subscribed to topic: %s', topic)

if len(sys.argv) < 2:
    print('Usage: {} <topic>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(PublisherComponent(), logging=logging.DEBUG)
