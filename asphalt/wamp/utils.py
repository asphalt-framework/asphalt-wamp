from typing import Callable, Union
from contextlib import closing
from pathlib import Path, PurePath
from tempfile import mkdtemp
import shutil
import atexit
import subprocess
import socket
import inspect
import sys

from typeguard import check_argument_types


def unwrap_function(func: Callable) -> Callable:
    unwrapped = func
    while hasattr(unwrapped, '__wrapped__'):
        unwrapped = unwrapped.__wrapped__

    return unwrapped


def validate_handler(handler: Callable, kind: str) -> None:
    unwrapped = handler
    while hasattr(unwrapped, '__wrapped__'):
        unwrapped = unwrapped.__wrapped__
        spec = inspect.getfullargspec(unwrapped)
        min_args = 2 if inspect.ismethod(unwrapped) else 1
        if not spec.varargs and len(spec.args) < min_args:
            raise TypeError('{} must accept at least one positional argument'.format(kind))


def get_next_free_tcp_port() -> int:
    """Return the next free TCP port on the ``localhost`` interface."""
    with closing(socket.socket()) as sock:
        sock.bind(('localhost', 0))
        return sock.getsockname()[1]


def launch_crossbar(directory: Union[str, PurePath]) -> None:
    """
    Launch an instance of the Crossbar WAMP router.

    :param directory: the directory containing the configuration file (must be writable)

    """
    process = subprocess.Popen([sys.executable, '-u', '-m', 'crossbar.controller.cli', 'start',
                                '--cbdir', str(directory)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Read output until a line is found that confirms the transport is ready
    for line in process.stdout:
        if b"transport 'transport1' started" in line:
            atexit.register(process.terminate)
            return

    raise RuntimeError('Crossbar failed to start: ' + process.stderr.read().decode())


def launch_adhoc_crossbar(config) -> int:
    """
    Launch an ad-hoc instance of the Crossbar WAMP router.

    This is a convenience function for testing purposes and should not be used in production.

    It writes the given configuration in a temporary directory and replaces ``%(port)s`` in the
    configuration with an ephemeral TCP port.

    If no configuration is given a default configuration is used where only anonymous
    authentication is defined and the anonymous user has all privileges on everything.
    One websocket transport is defined, listening on ``localhost``.

    The Crossbar process is automatically terminated and temporary directory deleted when the host
    process terminates.

    :param config: YAML configuration for crossbar (for ``config.yaml``)
    :return: the automatically selected port

    """
    check_argument_types()

    # Get the next available TCP port
    port = get_next_free_tcp_port()

    # Write the configuration file
    tempdir = Path(mkdtemp())
    atexit.register(shutil.rmtree, str(tempdir))
    config_file = tempdir / 'config.yaml'
    with config_file.open('w') as f:
        f.write(config % {'port': port})

    launch_crossbar(tempdir)
    return port
