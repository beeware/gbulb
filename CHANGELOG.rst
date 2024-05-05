Change Log
==========

.. towncrier release notes start

0.6.5 (2024-05-05)
==================

Features
--------

* Support for driving ``BufferedProtocol`` instances using ``sock_recv_into`` was added. (`#58 <https://github.com/beeware/briefcase/issues/58>`__)
* Support for Python 3.12 was added. (`#76 <https://github.com/beeware/briefcase/issues/76>`__)
* Support for Python 3.13 was added. (`#76 <https://github.com/beeware/briefcase/issues/76>`__)


Bugfixes
--------

* Support for using a generator as a co-routine has been removed, in line with the change in behavior in Python 3.12. Python 3.11 and earlier will still support this usage, but it is no longer verified as part of GBulb. (`#78 <https://github.com/beeware/briefcase/issues/78>`__)


Backward Incompatible Changes
-----------------------------

* Support for Python 3.7 was removed. (`#137 <https://github.com/beeware/briefcase/issues/137>`__)


Documentation
-------------

* The README badges were updated to display correctly on GitHub. (`#136 <https://github.com/beeware/briefcase/issues/136>`__)

Misc
----

* #68, #70, #71, #72, #74, #75, #77, #79, #80, #81, #82, #83, #84, #85, #86, #90, #91, #92, #93, #94, #95, #96, #97, #98, #99, #100, #101, #103, #104, #105, #106, #107, #108, #109, #112, #113, #114, #115, #118, #119, #120, #121, #122, #123, #124, #125, #126, #127, #128, #129, #130, #131, #132, #133, #134, #135


0.6.4 (2023-02-07)
------------------

Features
--------

* Support for Python 3.11 was added. (`#61 <https://github.com/beeware/gbulb/issues/61`__`)
* Initial support for Python 3.12 was added. (`#69 <https://github.com/beeware/gbulb/issues/69`__`)


Bugfixes
--------

* The GTK event loop no longer forces the use of the default GLib main context on every instance. (`#59 <https://github.com/beeware/gbulb/issues/59`__`)


Misc
----

* #62, #64


0.6.3 (2022-02-20)
------------------

Bugfixes
^^^^^^^^

* Corrected the import of ``InvalidStateError`` to fix an error seen on Python
  3.8+. (`#56 <https://github.com/beeware/gbulb/issues/56>`__)

* Reverted the fix from #47; that change led to file descriptor leaks. (`#52
  <https://github.com/beeware/gbulb/issues/52>`__)


0.6.2 (2021-10-24)
------------------

Features
^^^^^^^^

* Added support for Python 3.10. (`#50
  <https://github.com/beeware/gbulb/issues/50>`__)

Bugfixes
^^^^^^^^

* Corrects a problem where a socket isn't forgotten and causes 100% CPU load.
  (`#47 <https://github.com/beeware/gbulb/issues/47>`__)

Improved Documentation
^^^^^^^^^^^^^^^^^^^^^^

* #49


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
