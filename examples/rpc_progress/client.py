"""
This example demonstrates the use of the progress reporting feature in RPC calls.
It uses the feature to download a file from the server (server.py) in chunks.

First start server.py and take note of which port it's running on.
You will need to give this port number as the first argument to this script.

It's not very fast because there's quite a lot of overhead from the WAMP protocol, serialization
etc.
"""

from asyncio import coroutine
from pathlib import Path
from tempfile import mkdtemp
import logging
import sys

from asphalt.core.component import ContainerComponent
from asphalt.core.concurrency import stop_event_loop
from asphalt.core.context import Context
from asphalt.core.runner import run_application

logger = logging.getLogger(__name__)


class FileGetterComponent(ContainerComponent):
    @coroutine
    def start(self, ctx: Context):
        port = int(sys.argv[1])
        self.add_component('wamp', url='ws://localhost:{}'.format(port))
        yield from super().start(ctx)

        def on_progress(data: bytes):
            # This gets called for every chunk the server sends (ctx.progress() on the other side)
            outfile.write(data)
            print('\r{} bytes written'.format(outfile.tell()), end='')

        path = Path(mkdtemp()) / Path(sys.argv[2]).name
        with path.open('wb') as outfile:
            yield from ctx.wamp.call('send_file', sys.argv[2], on_progress=on_progress)
        print()

        logger.info('File saved as %s', path)
        stop_event_loop()

if len(sys.argv) < 3:
    print('Usage: {} <port> <file name>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(FileGetterComponent(), logging=logging.DEBUG)
