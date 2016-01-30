"""
This example demonstrates the use of the progress reporting feature in RPC calls.
It uses the feature to download a file from the server (server.py) in chunks to a temporary
directory.

The file path parameter should be a path relative to the directory where the server is serving
files from.
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
        self.add_component('wamp', url='ws://localhost:56666')
        yield from super().start(ctx)

        def on_progress(data: bytes):
            # This gets called for every chunk the server sends (ctx.progress() on the other side)
            outfile.write(data)
            print('\r{} bytes written'.format(outfile.tell()), end='')

        remote_path = sys.argv[1]
        local_path = Path(mkdtemp()) / Path(remote_path).name
        with local_path.open('wb') as outfile:
            yield from ctx.wamp.call('send_file', remote_path, on_progress=on_progress)
        print('File saved as %s' % local_path)

        stop_event_loop()

if len(sys.argv) < 2:
    print('Usage: {} <file path>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(FileGetterComponent(), logging=logging.DEBUG)
