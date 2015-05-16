import pytest


@pytest.fixture(scope='session')
def crossbar_config():
    return """\
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
    serializers: ['json', 'msgpack']
    endpoint:
      type: tcp
      interface: 127.0.0.1
      port: {port}
"""
