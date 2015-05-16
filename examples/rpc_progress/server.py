"""
This example demonstrates the use of the progress reporting feature in RPC calls.
It uses the feature to send files to the recipient in chunks.

It's not very fast because there's quite a lot of overheader
"""

from asyncio import coroutine
from pathlib import Path
import logging
import sys

from asphalt.core.component import ContainerComponent
from asphalt.core.concurrency import blocking
from asphalt.core.context import Context
from asphalt.core.runner import run_application
from asphalt.wamp.utils import launch_crossbar

logger = logging.getLogger(__name__)


@blocking
def send_file(ctx, path: str):
    final_path = ctx.base_path / path
    if not final_path.is_file():
        raise Exception('{} is not a file'.format(path))

    try:
        f = final_path.open('rb')
    except Exception:
        logger.exception('Error opening file')
        return

    with f:
        logger.info('Sending %s', path)
        data = f.read(65536)
        while data:
            ctx.progress(data)
            data = f.read(65536)

    logger.info('Finished sending %s', path)


class FileServerComponent(ContainerComponent):
    @coroutine
    def start(self, ctx: Context):
        port = launch_crossbar()
        url = 'ws://localhost:{}'.format(port)
        self.add_component('wamp', url=url)
        yield from super().start(ctx)

        ctx.base_path = Path(sys.argv[1])

        # Register the procedure handler as "send_file"
        yield from ctx.wamp.register(send_file, 'send_file')

        logger.info('Serving files from %s at %s', ctx.base_path, url)

if len(sys.argv) < 2:
    print('Specify the name of the directory that you wish to serve files from', file=sys.stderr)
    sys.exit(1)

run_application(FileServerComponent(), logging=logging.DEBUG)
