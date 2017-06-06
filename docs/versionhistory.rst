Version history
===============

This library adheres to `Semantic Versioning <http://semver.org/>`_.

**2.0.0**

- **BACKWARD INCOMPATIBLE** Upgraded minimum Autobahn version to v17.5.1
- **BACKWARD INCOMPATIBLE** Changed the default value of the ``path`` option on ``WAMPClient`` to
  ``/ws`` to match the default Crossbar configuration
- **BACKWARD INCOMPATIBLE** Changed subscriptions to use the ``details`` keyword argument to accept
  subscription details (since ``details_arg`` is now deprecated in Autobahn)
- **BACKWARD INCOMPATIBLE** Replaced ``SessionJoinEvent.session_id`` with the ``details`` attribute
  which directly exposes all session details provided by Autobahn
- Fixed error during ``WAMPClient.close()`` if a connection attempt was in progress
- Added compatibility with Asphalt 4.0
- Added the ``WAMPClient.details`` property which returns the session details when joined to one
- Added the ``concurrency`` option for procedure registration
- Added the ``get_retained`` option for subscription registration
- Added the ``retain`` option for ``WAMPClient.publish()``

**1.0.0** (2017-04-29)

- Initial release
