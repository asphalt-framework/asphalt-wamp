from contextlib import closing
from pathlib import Path
from tempfile import mkdtemp
from typing import Callable
import subprocess
import socket
import inspect
import sys


def validate_handler(handler: Callable, kind: str):
    unwrapped = handler
    while hasattr(unwrapped, '__wrapped__'):
        unwrapped = unwrapped.__wrapped__
        spec = inspect.getfullargspec(unwrapped)
        min_args = 2 if inspect.ismethod(unwrapped) else 1
        if not spec.varargs and len(spec.args) < min_args:
            raise TypeError('{} must accept at least one positional argument'.format(kind))

    return unwrapped


def get_next_free_tcp_port():
    with closing(socket.socket()) as sock:
        sock.bind(('localhost', 0))
        return sock.getsockname()[1]


def launch_crossbar(port: int=None) -> int:
    """
    Launch an ad-hoc instance of the Crossbar WAMP router.

    In this Crossbar instance, no authentication or authorization rules have been defined and the
    anonymous user has full privileges on everything.
    One websocket transport is defined, listening on ``localhost`` on the given port.
    If no port is given, the next free port will be used.

    Before writing the configuration file contents, :meth:`str.format` will be called on it
    with ``port`` as the only variable.

    :param port the port where the websocket transport will listen on
    :return: the port where the transport listens on

    """
    port = port or get_next_free_tcp_port()
    config = """\
---
controller: {{}}
workers:
- type: router
  realms:
  - name: default
    roles:
    - name: anonymous
      permissions:
      - {{call: true, publish: true, register: true, subscribe: true, uri: '*'}}
  transports:
  - type: websocket
    endpoint:
      type: tcp
      interface: localhost
      port: {port}
""".format(port=port)

    # Create a configuration file
    tempdir = Path(mkdtemp())
    config_file = tempdir / 'config.yaml'
    with config_file.open('w') as f:
        f.write(config)

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
            return port

    raise RuntimeError('crossbar failed to start: ' + process.stderr.read().decode())
