"""
This example demonstrates the use of the progress reporting feature in RPC calls.
It (ab)uses the feature to send files to the clients in chunks.

The command line argument should be a path to a directory where files will be served from.
"""

from pathlib import Path
import logging
import sys

from asyncio_extras.file import open_async

from asphalt.core import ContainerComponent, Context, run_application
from asphalt.wamp.context import CallContext
from asphalt.wamp.utils import launch_crossbar

logger = logging.getLogger(__name__)


async def send_file(ctx: CallContext, path: str):
    final_path = ctx.base_path / path
    if not final_path.is_file():
        raise Exception('{} is not a file'.format(path))

    async with open_async(final_path, 'rb') as f:
        logger.info('Sending %s', path)
        async for chunk in f.read_chunks(65536):
            ctx.progress(chunk)

    logger.info('Finished sending %s', path)


class FileServerComponent(ContainerComponent):
    async def start(self, ctx: Context):
        self.add_component('wamp', url='ws://localhost:8080')
        await super().start(ctx)

        ctx.base_path = Path(sys.argv[1])
        await ctx.wamp.register(send_file, 'send_file')

if len(sys.argv) < 2:
    print('Usage: {} <base directory>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(FileServerComponent(), logging=logging.INFO)
