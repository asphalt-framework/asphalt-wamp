Configuration
=============

.. highlight:: yaml

WAMP, being a routed protocol, requires a router to connect to. If you do not have one already,
the reference implementation, Crossbar_, should work nicely. The recommended way of setting it up
is with Docker_, though setting up a dedicated virtualenv_ for it would also do the trick.

Most WAMP clients need very little configuration. You usually have to set the realm name, host name
(if not running on localhost) and port (if not running on port 8080) and TLS, if connecting to a
remote instance securely.

Suppose you're connecting to realm ``myrealm`` on ``crossbar.example.org``, port 8181 using TLS,
your configuration would look like this::

    components:
        wamp:
          realm: myrealmname
          host: crossbar.example.org
          port: 8181
          tls: true

Your wamp client resource (``default``) would then be accessible on the context as ``ctx.wamp``.

Multiple clients
----------------

You can also configure multiple WAMP clients if necessary. For that, you will need to have a
structure along the lines of::

    components:
        wamp:
          tls: true
          clients:
            wamp1:
              realm: myrealmname
              host: crossbar.example.org
              port: 8181
            wamp2:
              realm: otherrealm
              host: crossbar.company.com

In this example, two client resources (``wamp1 / ctx.wamp1`` and ``wamp2 / ctx.wamp2``) are
created. The first one is like the one in the previous example. The second connects to the realm
named ``otherrealm`` on ``crossbar.company.com`` on the default port using TLS. Setting
``tls: true`` (or any other option) on the same level as ``clients`` means it's the default value
for all clients.

For a comprehensive list of all client options, see the documentation of the the
:class:`~asphalt.wamp.client.WAMPClient` class.

.. _Crossbar: http://crossbar.io/
.. _Docker: https://docs.docker.com/engine/installation/
.. _virtualenv: http://python-guide-pt-br.readthedocs.io/en/latest/dev/virtualenvs/