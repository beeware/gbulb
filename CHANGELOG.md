# Change Log
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
