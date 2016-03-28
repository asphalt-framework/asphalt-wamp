from asphalt.core.context import Context
import pytest
import txaio

from asphalt.wamp.utils import launch_adhoc_crossbar
from asphalt.wamp.client import WAMPClient

pytest_plugins = ['asphalt.core.pytest_plugin']


@pytest.fixture(scope='session')
def ws_url():
    port = launch_adhoc_crossbar("""\
---
version: 2
workers:
- type: router
  realms:
  - name: default
    roles:
    - name: authorized_users
      permissions:
      - uri: ''
        match: prefix
        allow: {call: true, publish: true, register: true, subscribe: true}
    - name: anonymous
      permissions:
      - uri: ''
        match: prefix
        allow: {call: true, publish: true, register: true, subscribe: true}
  transports:
  - type: websocket
    endpoint:
      type: tcp
      interface: localhost
      port: %(port)s
    auth:
      anonymous:
        type: static
        role: anonymous
      wampcra:
        type: static
        users:
          testuser:
            secret: testpass
            role: authorized_users
      ticket:
        type: static
        principals:
          device1:
            ticket: abc123
            role: authorized_users
""")
    return 'ws://localhost:{}/'.format(port)


@pytest.fixture(scope='session')
def setup_txaio():
    txaio.use_asyncio()


@pytest.yield_fixture
def wampclient(request, event_loop, ws_url, setup_txaio):
    kwargs = getattr(request, 'param', {})
    client = WAMPClient(ws_url, **kwargs)
    event_loop.run_until_complete(client.start(Context()))
    yield client
    event_loop.run_until_complete(client.disconnect())
