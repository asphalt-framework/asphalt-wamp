Version history
===============

This library adheres to `Semantic Versioning <http://semver.org/>`_.

**2.2.0** (2018-02-15)

- Added integration with asphalt-exceptions
- Raised connection logging level to ``INFO``
- Added a configurable shutdown timeout
- Renamed ``WAMPClient.close()`` to ``WAMPClient.stop()``
- Improved the reliability of the connection/session teardown process

**2.1.0** (2017-09-21)

- Added the ``protocol_options`` option to ``WAMPClient``
- Added the ``connection_timeout`` option to ``WAMPClient``

**2.0.1** (2017-06-07)

- Fixed failure to register option-less procedures and subscriptions added from a registry

**2.0.0** (2017-06-07)

- **BACKWARD INCOMPATIBLE** Upgraded minimum Autobahn version to v17.5.1
- **BACKWARD INCOMPATIBLE** Changed the default value of the ``path`` option on ``WAMPClient`` to
  ``/ws`` to match the default Crossbar configuration
- **BACKWARD INCOMPATIBLE** Changed subscriptions to use the ``details`` keyword argument to accept
  subscription details (since ``details_arg`` is now deprecated in Autobahn)
- **BACKWARD INCOMPATIBLE** Replaced ``SessionJoinEvent.session_id`` with the ``details`` attribute
  which directly exposes all session details provided by Autobahn
- **BACKWARD INCOMPATIBLE** Changed the way registration/subscription/call/publish options are
  passed. Keyword arguments were replaced with a single ``options`` keyword-only argument.
- **BACKWARD INCOMPATIBLE** Registry-based subscriptions and exception mappings now inherit the
  parent prefixes, just like procedures did previously
- Added compatibility with Asphalt 4.0
- Added the ``WAMPClient.details`` property which returns the session details when joined to one
- Fixed error during ``WAMPClient.close()`` if a connection attempt was in progress
- Fixed minor documentation errors

**1.0.0** (2017-04-29)

- Initial release
