"""
This example demonstrates the use of the progress reporting feature in RPC calls.
It (ab)uses the feature to download a file from the server (server.py) in chunks to a temporary
directory.

The file path parameter should be a path relative to the directory where the server is serving
files from.
"""

import asyncio
import logging
import sys
from pathlib import Path
from tempfile import mkdtemp

from asphalt.core import ContainerComponent, Context, run_application

logger = logging.getLogger(__name__)


class FileGetterComponent(ContainerComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:8080')
        await super().start(ctx)

        def on_progress(data: bytes):
            # This gets called for every chunk the server sends (ctx.progress() on the other side)
            outfile.write(data)
            print('\r{} bytes written'.format(outfile.tell()), end='')

        remote_path = sys.argv[1]
        local_path = Path(mkdtemp()) / Path(remote_path).name
        with local_path.open('wb') as outfile:
            await ctx.wamp.call('send_file', remote_path, on_progress=on_progress)

        print('\nFile saved as %s' % local_path)
        asyncio.get_event_loop().stop()

if len(sys.argv) < 2:
    print('Usage: {} <file path>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(FileGetterComponent(), logging=logging.INFO)
