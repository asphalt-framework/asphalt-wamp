Running the examples
====================

.. highlight:: bash

The examples in this directory tree require a running Crossbar_ instance with a specific
configuration. The ``.crossbar`` subdirectory contains a customized Crossbar configuration file
that will allow all the examples to work as intended. To use this configuration, start Crossbar
from the ``examples`` directory (assuming the ``crossbar`` command is on your ``PATH``)::

    crossbar start

If have Docker_ installed locally, you can instead use this script to launch it::

    ./crossbar-docker.sh

.. _Crossbar: http://crossbar.io/
.. _Docker: https://www.docker.com/