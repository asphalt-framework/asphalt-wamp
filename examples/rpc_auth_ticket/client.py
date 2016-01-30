"""
This example demonstrates how to authenticate against the WAMP router with the "ticket" method.
It will make a call to the server that returns with a message containing the authentication ID
of this client.
"""

from asyncio import coroutine
import logging

from asphalt.core.component import ContainerComponent
from asphalt.core.concurrency import stop_event_loop
from asphalt.core.context import Context
from asphalt.core.runner import run_application


class RPCClientComponent(ContainerComponent):
    @coroutine
    def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:56666', auth_method='ticket',
                           auth_id='testclient', auth_secret='client123')
        yield from super().start(ctx)

        result = yield from ctx.wamp.call('hello', disclose_me=True)
        print('Server responded: {}'.format(result))

        stop_event_loop()

run_application(RPCClientComponent(), logging=logging.DEBUG)
