"""
This example demonstrates the use of the progress reporting feature in RPC calls.
It (ab)uses the feature to download a file from the server (server.py) in chunks to a temporary
directory.

The file path parameter should be a path relative to the directory where the server is serving
files from.
"""

import logging
import sys
from pathlib import Path
from tempfile import mkdtemp

from asphalt.core import CLIApplicationComponent, Context, run_application
from asphalt.serialization.serializers.cbor import CBORSerializer

logger = logging.getLogger(__name__)


class FileGetterComponent(CLIApplicationComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', serializer=CBORSerializer())
        await super().start(ctx)

    async def run(self, ctx: Context):
        def on_progress(data: bytes):
            # This gets called for every chunk the server sends (ctx.progress() on the other side)
            outfile.write(data)
            print('\r{} bytes written'.format(outfile.tell()), end='')

        remote_path = sys.argv[1]
        local_path = Path(mkdtemp()) / Path(remote_path).name
        with local_path.open('wb') as outfile:
            await ctx.wamp.call('send_file', remote_path, on_progress=on_progress)

        print('\nFile saved as %s' % local_path)


if len(sys.argv) < 2:
    print('Usage: {} <file path>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(FileGetterComponent(), logging=logging.INFO)
