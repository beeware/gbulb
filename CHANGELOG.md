# Change Log
## [0.6.0] - 2018-08-06

### Fixed
 - Support for 3.7.

### Added
 - Preliminary Windows support. Please note that using subprocesses is known
   not to work. Patches welcome.

### Changed
 - Support for 3.4 and below has been dropped.

## [0.5.3] - 2017-01-27

### Fixed
 - Implemented child watcher setters and getters to allow writing tests with
   asynctest for code using gbulb.

 - `gbulb.install` now monkey patches `asyncio.SafeChildWatcher` to
   `gbulb.glib_events.GLibChildWatcher`, to ensure that any library code that
   uses it will use the correct child watcher.

## [0.5.2] - 2017-01-21

### Fixed
 - Fixed a sporadic test hang.

## [0.5.1] - 2017-01-20

### Fixed
 - Fixed breakage on Python versions older than 3.5.3, caused by 0.5.0. Thanks Brecht De Vlieger!

## [0.5] - 2017-01-12

### Fixed
 - Fixed issue with readers and writers not being added to the loop properly as
   a result of http://bugs.python.org/issue28369.

## [0.4] - 2016-10-26

### Fixed
 - gbulb will no longer allow you to schedule coroutines with call_at,
   call_soon and call_later, the same as asyncio.

## [0.3] - 2016-09-13

### Fixed
 - gbulb will no longer occasionally leak memory when used with threads.

## [0.2] - 2016-03-20
### Added
 - `gbulb.install` to simplify installation of a GLib-based event loop in
   asyncio
 - Connecting sockets now works as intended
 - Implement `call_soon_threadsafe`
 - Lots of tests

### Changed
 - **API BREAKAGE** No implicit Gtk import anymore. `GtkEventLoop` and `GtkEventLoopPolicy` have
   been moved to `gbulb.gtk`
 - **API BREAKAGE** No more `threads`, `default` or `full` parameters for event
   loop policy objects. gbulb now does nothing with threads
 - **API BREAKAGE** `gbulb.get_default_loop` has been removed
 - Permit running event loops recursively via `.run()`

### Fixed
 - Default signal handling of SIGINT
 - `gbulb.wait_signal.cancel()` now obeys the interface defined by
   `asyncio.Future`

## [0.1] - 2013-09-20
 - Initial release
