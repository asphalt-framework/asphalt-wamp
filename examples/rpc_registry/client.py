"""
This example WAMP client first calls the ``test.reverse`` remote method with string given as the
command line. It then publishes the return value on the ``topic.subtopic`` topic.
"""

from asyncio import coroutine
import logging
import sys

from asphalt.core.component import ContainerComponent
from asphalt.core.concurrency import stop_event_loop
from asphalt.core.context import Context
from asphalt.core.runner import run_application


class RPCClientComponent(ContainerComponent):
    @coroutine
    def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:56666')
        yield from super().start(ctx)

        message = sys.argv[1]
        result = yield from ctx.wamp.call('test.reverse', message)
        yield from ctx.wamp.publish('topic.subtopic', result)

        stop_event_loop()

if len(sys.argv) < 2:
    print('Usage: {} <text>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(RPCClientComponent(), logging=logging.DEBUG)
