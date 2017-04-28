Implementing dynamic authentication and authorization
=====================================================

While static configuration of users and permissions may work for trivial applications, you will
probably find yourself wanting for more flexibility for both authentication and authorization as
your application grows larger. Crossbar_, the reference WAMP router implementation, supports
*dynamic authentication* and *dynamic authorization*. That means that instead of a preconfigured
list of users or permissions, the router itself will call named remote procedures to determine
whether the credentials are valid (authentication) or whether a session has permission to
register/call a procedure or subscribe/publish to a topic (authorization).

The catch-22 in this is that the WAMP client that *provides* these procedures has to have
permission to register these procedures. This chicken and egg problem can be solved by providing
a trusted backdoor for this particular client. In the example below, the client providing the
authenticator and authorizer services connects via port 8081 which will be only made accessible for
that particular client. Unlike the other two configured roles, the ``server`` role has a static
authorization configuration, which is required for this to work.

.. code-block:: yaml

    version: 2
    workers:
    - type: router
      realms:
      - name: myrealm
        roles:
        - name: regular
          authorizer: authorize
        - name: admin
          authorizer: authorize
        - name: server
          permissions:
          - uri: "*"
            allow: {call: true, publish: true, register: true, subscribe: true}
      transports:
      - type: websocket
        endpoint:
          type: tcp
          port: 8080
        auth:
          ticket:
            type: dynamic
            authenticator: authenticate
      - type: websocket
        endpoint:
          type: tcp
          port: 8081
        auth:
          anonymous:
            type: static
            role: server

The client performing the ``server`` role will then register the ``authenticate()`` and
``authorize()`` procedures on the router::

    from typing import Dict

    from asphalt.core import ContainerComponent
    from asphalt.wamp import CallContext, WAMPRegistry
    from autobahn.wamp.exception import ApplicationError

    registry = WAMPRegistry()
    users = {
        'joe_average': ('1234', 'regular'),
        'bofh': ('B3yt&4_+', 'admin')
    }


    @registry.procedure
    def authenticate(ctx: CallContext, realm: str, auth_id: str, details: Dict[str, Any]):
        # Don't do this in real apps! This is a security hazard!
        # Instead, use a password hashing algorithm like argon2, scrypt or bcrypt
        user = users.get(authid)
        if user:
            # This applies for "ticket" authentication as configured above
            password, role = user
            if password == details['ticket']:
                return {'authrole': role}

        raise ApplicationError(ApplicationError.AUTHENTICATION_FAILED, 'Authentication failed')


    @registry.procedure
    def authorize(ctx: CallContext, session: Dict[str, Any], uri: str, action: str):
        # Cache any positive answers
        if session['authrole'] == 'regular':
            # Allow regular users to call and subscribe to public.*
            if action in ('call', 'subscribe') and uri.startswith('public.'):
                return {'allow': True, 'cache': True}
        elif session['authrole'] == 'admin':
            # Allow admins to call, subscribe and publish anything anywhere
            # (but not register procedures)
            if action in ('call', 'subscribe', 'publish'):
                return {'allow': True, 'cache': True}

        return {'allow': False}


    class ServerComponent(ContainerComponent):
        async def start(ctx):
            ctx.add_component('wamp', registry=registry)
            await super().start(ctx)

For more information, see the Crossbar documentation:

* `Dynamic authentication <http://crossbar.io/docs/Dynamic-Authenticators/>`_
* `Dynamic authorization <http://crossbar.io/docs/Authorization/#dynamic-authorization>`_

.. warning:: At the time of this writing (2017-04-29), caching of authorizer responses has not been
    implemented in Crossbar. This documentation assumes that it will be present in a future
    release.

.. _Crossbar: http://crossbar.io/
