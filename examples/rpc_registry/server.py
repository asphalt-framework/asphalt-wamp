"""
This example demonstrates the use of a WAMP registry to register a procedure handler and an event
subscriber.
"""

import logging

from asphalt.core import ContainerComponent, Context, run_application
from asphalt.wamp.context import CallContext, EventContext
from asphalt.wamp.registry import WAMPRegistry

topics = WAMPRegistry('topics')
procedures = WAMPRegistry('test')


@procedures.procedure
async def reverse(ctx: CallContext, message: str):
    return message[::-1]


@topics.subscriber('subtopic')
async def subtopic(ctx: EventContext, message):
    print('message received from topic.subtopic: %s' % message)


class RPCServerComponent(ContainerComponent):
    async def start(self, ctx: Context):
        registry = WAMPRegistry()
        registry.add_from(topics)
        registry.add_from(procedures)
        self.add_component('wamp', registry=registry)
        await super().start(ctx)
        await ctx.wamp.connect()


run_application(RPCServerComponent(), logging=logging.DEBUG)
