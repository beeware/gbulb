Change Log
==========

.. towncrier release notes start

0.6.3 (2022-02-20)
------------------

Bugfixes
^^^^^^^^

* Corrected the import of ``InvalidStateError`` to fix an error seen on Python 3.8+. (`#56 <https://github.com/beeware/gbulb/issues/56>`__)

* Reverted the fix from #47; that change led to file descriptor leaks. (`#52 <https://github.com/beeware/gbulb/issues/52>`_)


0.6.2 (2021-10-24)
------------------

Features
^^^^^^^^

* Added support for Python 3.10. (`#50 <https://github.com/beeware/gbulb/issues/50>`_)

Bugfixes
^^^^^^^^

* Corrects a problem where a socket isn't forgotten and causes 100% CPU load. (`#47 <https://github.com/beeware/gbulb/issues/47>`_)

Improved Documentation
^^^^^^^^^^^^^^^^^^^^^^

* (`#49 <https://github.com/beeware/gbulb/issues/49>`_)


0.6.1 (2018-08-09)
------------------

Bug fixes
^^^^^^^^^

* Support for 3.7, for real this time. Thank you Philippe Normand!

0.6.0 (2018-08-06)
------------------

Bug fixes
^^^^^^^^^

* Support for 3.7.

Features
^^^^^^^^

* Preliminary Windows support. Please note that using subprocesses is known
  not to work. Patches welcome.

Removals
^^^^^^^^

* Support for 3.4 and below has been dropped.

0.5.3 (2017-01-27)
------------------

Bug fixes
^^^^^^^^^

* Implemented child watcher setters and getters to allow writing tests with
   asynctest for code using gbulb.

* ``gbulb.install`` now monkey patches ``asyncio.SafeChildWatcher`` to
  ``gbulb.glib_events.GLibChildWatcher``, to ensure that any library code that
  uses it will use the correct child watcher.

0.5.2 (2017-01-21)
------------------

Bug fixes
^^^^^^^^^

* Fixed a sporadic test hang.

0.5.1 (2017-01-20)
------------------

Bug fixes
^^^^^^^^^

* Fixed breakage on Python versions older than 3.5.3, caused by 0.5.0. Thanks
  Brecht De Vlieger!

0.5 (2017-01-12)
----------------

Bug fixes
^^^^^^^^^

* Fixed issue with readers and writers not being added to the loop properly as
  a result of `Python Issue 28369 <https://bugs.python.org/issue28369>`__.

0.4 (2016-10-26)
----------------

Bug fixes
^^^^^^^^^

* gbulb will no longer allow you to schedule coroutines with ``call_at``,
  ``call_soon`` and ``call_later``, the same as asyncio.

0.3 (2016-09-13)
----------------

Bug fixes
^^^^^^^^^

* gbulb will no longer occasionally leak memory when used with threads.

0.2 (2016-03-20)
----------------

Features
^^^^^^^^

* ``gbulb.install`` to simplify installation of a GLib-based event loop in
   asyncio:
   - Connecting sockets now works as intended
   - Implement ``call_soon_threadsafe``
   - Lots of tests


* **API BREAKAGE** No implicit Gtk import anymore. ``GtkEventLoop`` and
  ``GtkEventLoopPolicy`` have been moved to ``gbulb.gtk``
* **API BREAKAGE** No more ``threads``, ``default`` or ``full`` parameters
  for event loop policy objects. gbulb now does nothing with threads.
* **API BREAKAGE** ``gbulb.get_default_loop`` has been removed
* Permit running event loops recursively via ``.run()``

Bug fixes
^^^^^^^^^

* Default signal handling of SIGINT
* ``gbulb.wait_signal.cancel()`` now obeys the interface defined by
  ``asyncio.Future``

0.1  2013-09-20
---------------

Features
^^^^^^^^

* Initial release
