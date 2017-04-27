"""
This example demonstrates the use of the progress reporting feature in RPC calls.
It (ab)uses the feature to send files to the clients in chunks.

The command line argument should be a path to a directory where files will be served from.
"""

from pathlib import Path
import logging
import sys

from asphalt.core import ContainerComponent, Context, run_application
from asphalt.serialization.serializers.cbor import CBORSerializer
from asphalt.wamp.context import CallContext
from async_generator import aclosing
from asyncio_extras.file import open_async

logger = logging.getLogger(__name__)


async def send_file(ctx: CallContext, path: str):
    final_path = ctx.base_path / path
    if not final_path.is_file():
        raise Exception('{} is not a file'.format(path))

    async with open_async(final_path, 'rb') as f:
        logger.info('Sending %s', path)
        async with aclosing(f.async_readchunks(65536)) as stream:
            async for chunk in stream:
                ctx.progress(chunk)

    logger.info('Finished sending %s', path)


class FileServerComponent(ContainerComponent):
    async def start(self, ctx: Context):
        # Need either msgpack or CBOR to serialize binary messages (such as raw file chunks)
        self.add_component('wamp', serializer=CBORSerializer())
        await super().start(ctx)

        ctx.base_path = Path(sys.argv[1])
        await ctx.wamp.register(send_file, 'send_file')


if len(sys.argv) < 2:
    print('Usage: {} <base directory>'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

run_application(FileServerComponent(), logging=logging.INFO)
