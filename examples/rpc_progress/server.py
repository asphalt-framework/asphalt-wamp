"""
This example demonstrates the use of the progress reporting feature in RPC calls.
It uses the feature to send files to the recipient in chunks.

The command line argument should be a path to a directory where files will be served from.
"""

from asyncio import coroutine
from pathlib import Path
import logging
import sys

from asphalt.core.component import ContainerComponent
from asphalt.core.concurrency import blocking
from asphalt.core.context import Context
from asphalt.core.runner import run_application
from asphalt.wamp.context import CallContext
from asphalt.wamp.utils import launch_crossbar

logger = logging.getLogger(__name__)


@blocking  # file I/O is a potentially blocking operation
def send_file(ctx: CallContext, path: str):
    final_path = ctx.base_path / path
    if not final_path.is_file():
        raise Exception('{} is not a file'.format(path))

    try:
        f = final_path.open('rb')
    except IOError:
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
        crossbar_dir = Path(__name__).parent / '.crossbar'
        launch_crossbar(crossbar_dir)

        self.add_component('wamp', url='ws://localhost:56666')
        yield from super().start(ctx)

        ctx.base_path = Path(sys.argv[1])
        yield from ctx.wamp.register_procedure(send_file, 'send_file')

if len(sys.argv) < 2:
    print('Usage: {} <base directory>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(FileServerComponent(), logging=logging.DEBUG)
