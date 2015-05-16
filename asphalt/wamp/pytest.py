"""Contains plugins for the py.test framework."""
from contextlib import closing
from pathlib import Path
from tempfile import mkdtemp
import subprocess
import shutil
import socket
import sys

from asphalt.core.context import Context
from asphalt.serialization.serializers.json import JSONSerializer
import pytest
import txaio


@pytest.yield_fixture(scope='session')
def crossbar(crossbar_config):
    assert isinstance(crossbar_config, str), \
        'the "crossbar_config" fixture must return a string (the YAML configuration for ' \
        'the Crossbar WAMP router)'

    # Get an available TCP port
    with closing(socket.socket()) as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]

    # Create a configuration file
    tempdir = Path(mkdtemp())
    config_file = tempdir / 'config.yaml'
    with config_file.open('w') as f:
        f.write(crossbar_config.format(port=port))

    # Launch crossbar in a subprocess
    bin_directory = 'Scripts' if sys.platform == 'win32' else 'bin'
    bin_path = Path(sys.prefix) / bin_directory / 'crossbar'
    process = subprocess.Popen([str(bin_path), 'start', '--cbdir', str(tempdir)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env={'PYTHONUNBUFFERED': '1'})

    # Read output until a line is found that confirms the transport is
    # ready
    for line in process.stdout:
        if b"transport 'transport1' started" in line:
            break
    else:
        raise RuntimeError('crossbar failed to start: ' + process.stderr.read().decode())

    yield 'ws://127.0.0.1:{}/'.format(port)
    process.terminate()
    shutil.rmtree(str(tempdir))


@pytest.fixture(scope='session')
def setup_txaio():
    txaio.use_asyncio()


@pytest.yield_fixture
def wampclient(event_loop, crossbar, setup_txaio):
    from asphalt.wamp.client import WAMPClient

    client = WAMPClient(Context(), 'default', crossbar, None, None, JSONSerializer(), True, True,
                        True)
    yield client
    event_loop.run_until_complete(client.disconnect())
