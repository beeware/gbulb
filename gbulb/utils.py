import asyncio
import weakref

__all__ = ['install', 'get_event_loop', 'wait_signal']

_gtk_available = None


def gtk_available():  #pragma: no cover
    global _gtk_available
    if _gtk_available is None:
        try:
            from gi.repository import Gtk
        except ImportError:
            Gtk = None

        _gtk_available = bool(Gtk)
    return _gtk_available


def install(gtk=False):
    """Set the default event loop policy.

    Call this as early as possible to ensure everything has a reference to the
    correct event loop.

    Set ``gtk`` to True if you intend to use Gtk in your application.

    If ``gtk`` is True and Gtk is not available, will raise `ValueError`.
    """

    if gtk:
        if not gtk_available():
            raise ValueError("Gtk is not available")
        else:
            from .glib_events import GtkEventLoopPolicy
            policy = GtkEventLoopPolicy()
    else:
        from .glib_events import GLibEventLoopPolicy
        policy = GLibEventLoopPolicy()

    asyncio.set_event_loop_policy(policy)


def get_event_loop():
    """Alias to asyncio.get_event_loop()."""
    return asyncio.get_event_loop()


class wait_signal(asyncio.Future):
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
