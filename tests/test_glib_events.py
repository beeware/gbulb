import pytest

from unittest import mock
from gi.repository import Gio

try:
    from gi.repository import Gtk
except ImportError:
    Gtk = None


@pytest.fixture
def glib_policy():
    from gbulb.glib_events import GLibEventLoopPolicy
    return GLibEventLoopPolicy()


@pytest.fixture
def gtk_policy():
    from gbulb.glib_events import GtkEventLoopPolicy
    return GtkEventLoopPolicy()


@pytest.yield_fixture(scope='function')
def glib_loop(glib_policy):
    l = glib_policy.new_event_loop()

    yield l

    l.close()


@pytest.yield_fixture(scope='function')
def gtk_loop(gtk_policy):
    l = gtk_policy.new_event_loop()

    yield l

    l.close()


class TestGLibEventLoopPolicy:
    def test_new_event_loop(self, glib_policy):
        a = glib_policy.new_event_loop()
        b = glib_policy.new_event_loop()

        assert a == glib_policy.get_default_loop()
        assert b != glib_policy.get_default_loop()

    def test_new_event_loop_application(self, glib_policy):
        a = glib_policy.new_event_loop()
        a.set_application(Gio.Application())
        b = glib_policy.new_event_loop()

        assert b._application is None


@pytest.mark.skipif(not Gtk, reason="Gtk is not available")
class TestGtkEventLoopPolicy:
    def test_new_event_loop(self, gtk_policy):
        from gbulb.glib_events import GtkEventLoop
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


class TestGLibEventLoop:
    def test_run(self, glib_loop):
        with mock.patch.object(glib_loop, '_mainloop') as ml:
            glib_loop.run()
            ml.run.assert_any_call()

        glib_loop.set_application(Gio.Application())

        with mock.patch.object(glib_loop, '_application') as app:
            glib_loop.run()
            app.run.assert_any_call(None)

    def test_stop(self, glib_loop):
        with mock.patch.object(glib_loop, '_mainloop') as ml:
            glib_loop.stop()
            ml.quit.assert_any_call()

        glib_loop.set_application(Gio.Application())

        with mock.patch.object(glib_loop, '_application') as app:
            glib_loop.stop()
            app.quit.assert_any_call()

    def test_set_application(self, glib_loop):
        assert glib_loop._application is None
        assert glib_loop._policy._application is None

        app = Gio.Application()
        glib_loop.set_application(app)

        assert glib_loop._application == app
        assert glib_loop._policy._application == app

    def test_set_application_invalid_type(self, glib_loop):
        with pytest.raises(TypeError):
            glib_loop.set_application(None)

    def test_set_application_invalid_repeat_calls(self, glib_loop):
        app = Gio.Application()
        glib_loop.set_application(app)

        with pytest.raises(ValueError):
            glib_loop.set_application(app)

    def test_set_application_invalid_when_running(self, glib_loop):
        app = Gio.Application()

        with pytest.raises(RuntimeError):
            with mock.patch.object(glib_loop, 'is_running', return_value=True):
                glib_loop.set_application(app)
