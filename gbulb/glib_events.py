"""PEP 3156 event loop based on GLib"""

import os
import signal
import threading
import weakref
from asyncio import events, futures, tasks, unix_events
from asyncio.log import logger

from gi.repository import GLib, Gio

from .utils import gtk_available

__all__ = ['GLibEventLoop', 'GLibEventLoopPolicy']


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
        source.set_callback(self.__callback__, self)
        source.attach(loop._context)
        loop._handlers.add(self)

    def cancel(self):
        super().cancel()
        self._source.destroy()
        self._loop._handlers.discard(self)

    def _run(self):
        self._ready = False
        super()._run()

    def __callback__(self, ignore_self):
        if not self._ready:
            self._ready = True

        # __callback__ is called within the MainContext object, which is
        # important in case that code includes a `Gtk.main()` or some such.
        # Otherwise what happens is the loop is started recursively, but the
        # callbacks don't finish firing, so they can't be rescheduled.
        self._run()
        if not self._repeat:
            self._loop._handlers.discard(self)
        return self._repeat


class BaseGLibEventLoop(unix_events.SelectorEventLoop):
    """GLib base event loop

    This class handles only the operations related to Glib.MainContext objects.

    Glib.MainLoop operations are implemented in the derived classes.
    """

    class DefaultSigINTHandler:
        def __init__(self):
            s = GLib.unix_signal_source_new(signal.SIGINT)
            s.set_callback(self.__callback__, self)
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

        def __callback__(self, ignore_self):
            if self._loop:
                l = self._loop()
                if l:
                    def interrupt(loop):
                        loop._interrupted = True
                        loop.stop()

                    l.call_soon_threadsafe(interrupt, l)
            return True

    # FIXME: only do this on init because otherwise just importing this module breaks SIGINT
    _default_sigint_handler = DefaultSigINTHandler()

    def __init__(self):
        self._readers = {}
        self._writers = {}
        self._sighandlers = {}
        self._chldhandlers = {}
        self._handlers = set()
        self._interrupted = False

        # install a default handler for SIGINT
        # in the default context
        if self._context == GLib.main_context_default():
            self._default_sigint_handler.attach(self)

        super().__init__()

    def create_task(self, coro):
        task = tasks.Task(coro, loop=self)
        if task._source_traceback:
            del task._source_traceback[-1]
        return task

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
            raise RuntimeError(
                "Recursively calling run_forever is forbidden. "
                "To recursively run the event loop, call run().")

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
        return self._running

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

        self._default_sigint_handler.detach(self)

        super().close()

    # Methods scheduling callbacks.  All these return Handles.
    def call_soon(self, callback, *args):
        return self.call_later(0, callback, *args)

    def call_later(self, delay, callback, *args):
        return GLibHandle(
                self,
                GLib.Timeout(delay*1000) if delay > 0 else GLib.Idle(),
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
    def __init__(self, *, context=None, application=None):
        self._context = context or GLib.MainContext()
        self._application = application
        self._running = False

        if application is None:
            # We use the introspected MainLoop object directly, because the
            # override in pygobject tampers with SIGINT
            self._mainloop = GLib._introspection_module.MainLoop.new(self._context, True)
        super().__init__()

    def run(self):
        recursive = self.is_running()

        self._running = True
        try:
            if self._application is not None:
                self._application.run(None)
            else:
                self._mainloop.run()
        finally:
            if not recursive:
                self._running = False

    def stop(self):
        """Stop the inner-most invocation of the event loop.

        Typically, this will mean stopping the event loop completely.

        Note that due to the nature of GLib's main loop, stopping may not be
        immediate.
        """

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
        l = GLibEventLoop(
            context=GLib.main_context_default(), application=self._application)
        l._policy = self
        return l


if gtk_available():
    __all__.extend(['GtkEventLoop', 'GtkEventLoopPolicy'])

    from gi.repository import Gtk

    class GtkEventLoop(GLibEventLoop):
        """Gtk-based event loop.

        This loop supports recursion in Gtk, for example for implementing modal
        windows.
        """
        def __init__(self, **kwargs):
            self._recursive = 0
            self._recurselock = threading.Lock()
            kwargs['context'] = GLib.main_context_default()

            super().__init__(**kwargs)

        def run(self):
            """Run the event loop until Gtk.main_quit is called.

            May be called multiple times to recursively start it again. This
            is useful for implementing asynchronous-like dialogs in code that
            is otherwise not asynchronous, for example modal dialogs.
            """
            if self.is_running():
                with self._recurselock:
                    self._recursive += 1
                try:
                    Gtk.main()
                finally:
                    with self._recurselock:
                        self._recursive -= 1
            else:
                super().run()

        def stop(self):
            """Stop the inner-most event loop.

            If it's also the outer-most event loop, the event loop will stop.
            """
            with self._recurselock:
                r = self._recursive
            if r > 0:
                Gtk.main_quit()
            else:
                super().stop()

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
