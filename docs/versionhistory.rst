Version history
===============

This library adheres to `Semantic Versioning <http://semver.org/>`_.

**2.0.0**

- **BACKWARD INCOMPATIBLE** Upgraded minimum Autobahn version to v17.5.1
- **BACKWARD INCOMPATIBLE** Changed the default value of the ``path`` option on ``WAMPClient`` to
  ``/ws`` to match the default Crossbar configuration
- Fixed error during ``WAMPClient.close()`` if a connection attempt was in progress

**1.0.0** (2017-04-29)

- Initial release
