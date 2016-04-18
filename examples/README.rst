Running the examples
====================

.. highlight:: bash

The examples in this directory tree require a running Crossbar_ instance with a specific
configuration. The ``.crossbar`` subdirectory contains a customized Crossbar configuration file
that will allow all the examples to work as intended. To use this configuration, start Crossbar
from the ``examples`` directory::

    crossbar start

If you're running Crossbar through Docker, you can use the customized configuration like this::

    docker run --rm -p 8080:8080 -v \
    $PWD/.crossbar/config.yaml:/var/crossbar/.crossbar/crossbar.yaml:ro crossbario/crossbar \
    --config /var/crossbar/.crossbar/crossbar.yaml

.. _Crossbar: http://crossbar.io/
