"""This example demonstrates how to find out the caller's authentication ID (username)."""

from asyncio import coroutine
from pathlib import Path
import logging

from asphalt.core.component import ContainerComponent
from asphalt.core.context import Context
from asphalt.core.runner import run_application
from asphalt.wamp.context import CallContext
from asphalt.wamp.utils import launch_crossbar


@coroutine
def hello(ctx: CallContext):
    session_info = yield from ctx.wamp.call('wamp.session.get', ctx.caller_session_id)
    return 'Hello, {}!'.format(session_info['authid'])


class RPCServerComponent(ContainerComponent):
    @coroutine
    def start(self, ctx: Context):
        crossbar_dir = Path(__name__).parent / '.crossbar'
        launch_crossbar(crossbar_dir)

        self.add_component('wamp', url='ws://localhost:56666', auth_method='wampcra',
                           auth_id='testserver', auth_secret='server123')
        yield from super().start(ctx)

        yield from ctx.wamp.register_procedure(hello, 'hello')

run_application(RPCServerComponent(), logging=logging.DEBUG)
