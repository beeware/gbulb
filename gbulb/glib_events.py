"""PEP 3156 event loop based on GLib"""

from gi.repository import GLib, Gio
try:
    from gi.repository import Gtk
except ImportError:
    Gtk = None

import collections
import os
import signal
import threading
import weakref
from asyncio import events, futures, tasks, unix_events
from asyncio.log import logger


class GLibChildWatcher(unix_events.AbstractChildWatcher):
    def __init__(self):
        self._sources = {}

    def attach_loop(self, loop):
        # just ignored
        pass

    def add_child_handler(self, pid, callback, *args):
        self.remove_child_handler(pid)

        source = GLib.child_watch_add(0, pid, self._glib_callback)
        self._sources[pid] = source, callback, args

    def remove_child_handler(self, pid):
        try:
            source = self._sources.pop(pid)[0]
        except KeyError:
            return False

        GLib.source_remove(source)
        return True

    def close(self):
        for source, callback, args in self._sources.values():
            GLib.source_remove(source)

    def __enter__(self):
        return self

    def __exit__(self, a, b, c):
        pass

    def _glib_callback(self, pid, status):

        try:
            source, callback, args = self._sources.pop(pid)
        except KeyError:
            return

        GLib.source_remove(source)

        if os.WIFSIGNALED(status):
            returncode = -os.WTERMSIG(status)
        elif os.WIFEXITED(status):
            returncode = os.WEXITSTATUS(status)

            #FIXME: Hack for adjusting invalid status returned by GLIB
            #    Looks like there is a bug in glib or in pygobject
            if returncode > 128:
                returncode = 128 - returncode
        else:
            returncode = status

        callback(pid, returncode, *args)


class GLibHandle(events.Handle):
    def __init__(self, loop, source, repeat, callback, args):
        super().__init__(callback, args, loop)

        self._loop = loop
        self._source = source
        self._repeat = repeat
        self._ready = False
        source.set_callback(self.__class__._callback, self)
        source.attach(loop._context)
        loop._handlers.add(self)

    def cancel(self):
        super().cancel()
        self._source.destroy()
        self._loop._handlers.discard(self)

    def _run(self):
        self._ready = False
        super()._run()

    def _callback(self):
        if not self._ready:
            self._ready = True
            self._loop._ready.append(self)

        self._loop._dispatch()

        if not self._repeat:
            self._loop._handlers.discard(self)
        return self._repeat

#
# Divergences with PEP 3156
#
# In GLib, the concept of event loop is split in two classes: GLib.MainContext
# and GLib.MainLoop.
#
# The thing is mostly implemented by MainContext. MainLoop is just a wrapper
# that implements the run() and quit() functions. MainLoop.run() atomically
# acquires a MainContext and repeatedly calls MainContext.iteration() until
# MainLoop.quit() is called.
#
# A MainContext is not bound to a particular thread, however is cannot be used
# by multiple threads concurrently. If the context is owned by another thread,
# then MainLoop.run() will block until the context is released by the other
# thread.
#
# MainLoop.run() may be called recursively by the same thread (this is mainly
# used for implementing modal dialogs in Gtk).
#
#
# The issue: given a context, GLib provides no ways to know if there is an
# existing event loop running for that context. It implies the following
# divergences with PEP 3156:
#
#  - .run_forever() and .run_until_complete() are not guaranteed to run
#    immediatly. If the context is owned by another thread, then they will
#    block until the context is released by the other thread.
#
#  - .stop() is relevant only when the currently running Glib.MainLoop object
#    was created by this asyncio object (i.e. by calling .run_forever() or
#    .run_until_complete()). The event loop will quit only when it regains
#    control of the context. This can happen in two cases:
#     1. when multiple event loop are enclosed (by creating new MainLoop
#        objects and calling .run() recursively)
#     2. when the event loop has not even yet started because it is still
#        trying to acquire the context
#
# It should be wiser not to use any recursion at all. GLibEventLoop will
# actually prevent you from doing that (in accordance with PEP 3156). However
# you should keep in mind that enclosed loops may be started at any time by
# third-party code calling directly GLib's primitives.
#
#
# TODO: documentation about signal GLib allows catching signals from any
# thread. It is dispatched to the first handler whose flag is not yet raised.
#
# about SIGINT -> KeyboardInterrupt will never be raised asynchronously


class BaseGLibEventLoop(unix_events.SelectorEventLoop):
    """GLib base event loop

    This class handles only the operations related to Glib.MainContext objects.

    Glib.MainLoop operations are implemented in the derived classes.
    """

    class DefaultSigINTHandler:
        def __init__(self):
            s = GLib.unix_signal_source_new(signal.SIGINT)
            s.set_callback(self.__class__._callback, self)
            s.attach()

            self._source = s
            self._loop = None

        def attach(self, loop):
            if self._loop:
                l = self._loop()
                if l and l != loop:
                    logger.warning(
                        "Multiple event loops for the GLib default context. "
                        "SIGINT may not be caught reliably")

            self._loop = weakref.ref(loop)

        def detach(self, loop):
            if self._loop:
                l = self._loop()
                if l == loop:
                    self._loop = None

        def _callback(self):
            if self._loop:
                l = self._loop()
                if l:
                    def interrupt(loop):
                        loop._interrupted = True
                        loop.stop()

                    l.call_soon_threadsafe(interrupt, l)
            return True

    _default_sigint_handler = DefaultSigINTHandler()

    def __init__(self):
        self._readers = {}
        self._writers = {}
        self._sighandlers = {}
        self._chldhandlers = {}
        self._handlers = set()
        self._ready = collections.deque()
        self._wakeup = None
        self._will_dispatch = False
        self._interrupted = False

        # install a default handler for SIGINT
        # in the default context
        if self._context == GLib.main_context_default():
            self._default_sigint_handler.attach(self)

        self._runlock = threading.Lock()
        super().__init__()

    def create_task(self, coro):
        task = tasks.Task(coro, loop=self)
        if task._source_traceback:
            del task._source_traceback[-1]
        return task

    def _dispatch(self):
        # This is the only place where callbacks are actually *called*. All
        # other places just add them to ready. Note: We run all currently
        # scheduled callbacks, but not any callbacks scheduled by callbacks run
        # this time around -- they will be run the next time (after another I/O
        # poll). Use an idiom that is threadsafe without using locks.

        self._will_dispatch = True

        ntodo = len(self._ready)
        for i in range(ntodo):
            handle = self._ready.popleft()
            if not handle._cancelled:
                handle._run()

        self._schedule_dispatch()
        self._will_dispatch = False

    def _schedule_dispatch(self):
        if not self._ready or self._wakeup is not None:
            return

        def wakeup_cb(self):
            self._dispatch()
            if self._ready:
                return True
            else:
                self._wakeup.destroy()
                self._wakeup = None
                return False

        self._wakeup = GLib.Timeout(0)
        self._wakeup.set_callback(wakeup_cb, self)
        self._wakeup.attach(self._context)

    def run_until_complete(self, future, **kw):
        """Run the event loop until a Future is done.

        Return the Future's result, or raise its exception.
        """

        def stop(f):
            self.stop()

        future = tasks.async(future, loop=self)
        future.add_done_callback(stop)
        try:
            self.run_forever(**kw)
        finally:
            future.remove_done_callback(stop)

        if not future.done():
            raise RuntimeError('Event loop stopped before Future completed.')

        return future.result()

    def run_forever(self):
        """Run the event loop until stop() is called."""

        if self.is_running():
            raise RuntimeError('Event loop is running.')

        with self._runlock:
            # We do not run the callbacks immediately. We need to call them
            # when the Gtk loop is running, in case one callback calls .stop()
            self._schedule_dispatch()

            try:
                self.run()
            finally:
                self.stop()

            if self._interrupted:
                # ._interrupted is set when SIGINT is caught be the default
                # signal handler implemented in this module.
                #
                # If no user-defined handler is registered, then the default
                # behaviour is just to raise KeyboardInterrupt
                #
                self._interrupted = False
                raise KeyboardInterrupt()

    def is_running(self):
        """Return whether the event loop is currently running."""
        return self._runlock.locked()

    def stop(self):
        """Stop the event loop as soon as reasonable.

        Exactly how soon that is may depend on the implementation, but
        no more I/O callbacks should be scheduled.
        """
        raise NotImplementedError()

    def close(self):
        for fd in list(self._readers):
            self.remove_reader(fd)

        for fd in list(self._writers):
            self.remove_writer(fd)

        for sig in list(self._sighandlers):
            self.remove_signal_handler(sig)

        for pid in list(self._chldhandlers):
            self._remove_child_handler(pid)

        for s in list(self._handlers):
            s.cancel()

        self._ready.clear()

        self._default_sigint_handler.detach(self)

        super().close()

    # Methods scheduling callbacks.  All these return Handles.
    def call_soon(self, callback, *args):
        h = events.Handle(callback, args, self)
        self._ready.append(h)
        if not self._will_dispatch:
            self._schedule_dispatch()
        return h

    def call_later(self, delay, callback, *args):

        if delay <= 0:
            return self.call_soon(callback, *args)
        else:
            return GLibHandle(
                self,
                GLib.Timeout(delay*1000 if delay > 0 else 0),
                False,
                callback, args)

    def call_at(self, when, callback, *args):
        return self.call_later(when - self.time(), callback, *args)

    def time(self):
        return GLib.get_monotonic_time() / 1000000

    # FIXME: these functions are not available on windows
    def add_reader(self, fd, callback, *args):
        if not isinstance(fd, int):
            fd = fd.fileno()

        self.remove_reader(fd)

        s = GLib.unix_fd_source_new(fd, GLib.IO_IN)

        assert fd not in self._readers
        self._readers[fd] = GLibHandle(self, s, True, callback, args)

    def remove_reader(self, fd):
        if not isinstance(fd, int):
            fd = fd.fileno()

        try:
            self._readers.pop(fd).cancel()
            return True

        except KeyError:
            return False

    def add_writer(self, fd, callback, *args):
        if not isinstance(fd, int):
            fd = fd.fileno()

        self.remove_writer(fd)

        s = GLib.unix_fd_source_new(fd, GLib.IO_OUT)

        assert fd not in self._writers
        self._writers[fd] = GLibHandle(self, s, True, callback, args)

    def remove_writer(self, fd):
        if not isinstance(fd, int):
            fd = fd.fileno()

        try:
            self._writers.pop(fd).cancel()
            return True

        except KeyError:
            return False

    # Signal handling.

    def add_signal_handler(self, sig, callback, *args):
        self._check_signal(sig)
        self.remove_signal_handler(sig)

        s = GLib.unix_signal_source_new(sig)
        if s is None:
            if sig == signal.SIGKILL:
                raise RuntimeError("cannot catch SIGKILL")
            else:
                raise ValueError("signal not supported")

        assert sig not in self._sighandlers
        self._sighandlers[sig] = GLibHandle(self, s, True, callback, args)

    def remove_signal_handler(self, sig):
        self._check_signal(sig)
        try:
            self._sighandlers.pop(sig).cancel()
            return True

        except KeyError:
            return False


class GLibEventLoop(BaseGLibEventLoop):
    def __init__(self, context=None, application=None):
        self._context = context or GLib.MainContext()
        self._application = application

        if application is None:
            # We use the introspected MainLoop object directly, because the
            # override in pygobject tampers with SIGINT
            self._mainloop = GLib._introspection_module.MainLoop.new(self._context, True)
        super().__init__()

    def run(self):
        if self._application is not None:
            self._application.run(None)
        else:
            self._mainloop.run()

    def stop(self):
        if self._application is not None:
            self._application.quit()
        else:
            self._mainloop.quit()

    def run_forever(self, application=None):
        """Run the event loop until stop() is called."""

        if application is not None:
            self.set_application(application)
        super().run_forever()

    def set_application(self, application):
        if not isinstance(application, Gio.Application):
            raise TypeError("application must be a Gio.Application object")
        if self._application is not None:
            raise ValueError("application is already set")
        if self.is_running():
            raise RuntimeError("You can't add the application to a loop that's already running.")
        self._application = application
        self._policy._application = application
        del self._mainloop


class GLibEventLoopPolicy(events.AbstractEventLoopPolicy):
    """Default GLib event loop policy

    In this policy, each thread has its own event loop.  However, we only
    automatically create an event loop by default for the main thread; other
    threads by default have no event loop.
    """

    #TODO add a parameter to synchronise with GLib's thread default contexts
    #   (g_main_context_push_thread_default())
    def __init__(self, application=None):
        self._default_loop = None
        self._application = application

        # WTF? can I get rid of this?
        self._policy = unix_events.DefaultEventLoopPolicy()
        self._policy.new_event_loop = self.new_event_loop
        self.get_event_loop = self._policy.get_event_loop
        self.set_event_loop = self._policy.set_event_loop
        self.get_child_watcher = self._policy.get_child_watcher

        self._policy.set_child_watcher(GLibChildWatcher())

    def new_event_loop(self):
        """Create a new event loop and return it."""
        if not self._default_loop and isinstance(threading.current_thread(), threading._MainThread):
            l = self.get_default_loop()
        else:
            l = GLibEventLoop()
        l._policy = self

        return l

    def get_default_loop(self):
        """Get the default event loop."""
        if not self._default_loop:
            self._default_loop = self._new_default_loop()
        return self._default_loop

    def _new_default_loop(self):
        return GLibEventLoop(
            GLib.main_context_default(), application=self._application)


if Gtk:
    class GtkEventLoop(GLibEventLoop):
        """Gtk-based event loop."""
        def __init__(self, *args, **kwargs):
            self._context = GLib.main_context_default()
            super().__init__(*args, **kwargs)

        def run(self):
            if self._application is not None:
                super().run()
            else:
                Gtk.main()

        def stop(self):
            if self._application is not None:
                super().stop()
            else:
                Gtk.main_quit()

    class GtkEventLoopPolicy(GLibEventLoopPolicy):
        """Gtk-based event loop policy. Use this if you are using Gtk."""
        def _new_default_loop(self):
            l = GtkEventLoop(application=self._application)
            l._policy = self
            return l

        def new_event_loop(self):
            if not self._default_loop:
                l = self.get_default_loop()
            else:
                l = GtkEventLoop()
            l._policy = self
            return l


class wait_signal(futures.Future):
    """A future for waiting for a given signal to occur."""

    def __init__(self, obj, name, *, loop=None):
        super().__init__(loop=loop)
        self._obj = weakref.ref(obj, self.cancel)
        self._hnd = obj.connect(name, self._signal_callback)

    def _signal_callback(self, *k):
        obj = self._obj()
        if obj is not None:
            obj.disconnect(self._hnd)
        self.set_result(k)

    def cancel(self):
        super().cancel()
        obj = self._obj()
        if obj is not None:
            obj.disconnect(self._hnd)
