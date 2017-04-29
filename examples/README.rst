Running the examples
====================

The examples in this directory tree require a running WAMP router with a specific configuration.
The fastest way to get it up and running is by using the supplied docker-compose_ configuration
(``crossbar-config.yaml``). To use this configuration, make sure you have Docker_ and
docker-compose_ installed and then run:

.. code-block:: bash

    docker-compose up -d

.. _Docker: https://docs.docker.com/engine/installation/
.. _docker-compose: https://docs.docker.com/compose/install/
