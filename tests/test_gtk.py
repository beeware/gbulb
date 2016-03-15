import pytest

from utils import gtk_loop, gtk_policy

try:
    from gi.repository import Gtk
except ImportError:  # pragma: no cover
    Gtk = None


@pytest.mark.skipif(not Gtk, reason="Gtk is not available")
class TestGtkEventLoopPolicy:
    def test_new_event_loop(self, gtk_policy):
        from gbulb.gtk import GtkEventLoop
        a = gtk_policy.new_event_loop()
        b = gtk_policy.new_event_loop()

        assert isinstance(a, GtkEventLoop)
        assert isinstance(b, GtkEventLoop)
        assert a != b
        assert a == gtk_policy.get_default_loop()

    def test_new_event_loop_application(self, gtk_policy):
        a = gtk_policy.new_event_loop()
        a.set_application(Gtk.Application())
        b = gtk_policy.new_event_loop()

        assert b._application is None

    def test_event_loop_recursion(self, gtk_loop):
        loop_count = 0

        def inner():
            nonlocal loop_count
            i = loop_count
            print('starting loop', loop_count)
            loop_count += 1

            if loop_count == 10:
                print('loop {} stopped'.format(i))
                gtk_loop.stop()
            else:
                gtk_loop.call_soon(inner)
                gtk_loop.run()
                print('loop {} stopped'.format(i))
                gtk_loop.stop()

        gtk_loop.call_soon(inner)
        gtk_loop.run_forever()

        assert loop_count == 10
