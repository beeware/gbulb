import threading

from gi.repository import Gtk

from .glib_events import GLibEventLoop, GLibEventLoopPolicy

__all__ = ["GtkEventLoop", "GtkEventLoopPolicy"]


class GtkEventLoop(GLibEventLoop):
    """Gtk-based event loop.

    This loop supports recursion in Gtk, for example for implementing
    modal windows.
    """

    def __init__(self, **kwargs):
        self._recursive = 0
        self._recurselock = threading.Lock()

        super().__init__(**kwargs)

    def run(self):
        """Run the event loop until Gtk.main_quit is called.

        May be called multiple times to recursively start it again. This
        is useful for implementing asynchronous-like dialogs in code
        that is otherwise not asynchronous, for example modal dialogs.
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

        If it's also the outer-most event loop, the event loop will
        stop.
        """
        with self._recurselock:
            r = self._recursive
        if r > 0:
            Gtk.main_quit()
        else:
            super().stop()


class GtkEventLoopPolicy(GLibEventLoopPolicy):
    """Gtk-based event loop policy.

    Use this if you are using Gtk.
    """

    EventLoopCls = GtkEventLoop
