from unittest import mock

import pytest

from utils import glib_loop


@pytest.mark.parametrize('gtk,gtk_available', [
    (False, False),
    (False, True),
    (True, False),
    (True, True),
])
def test_install(gtk, gtk_available):
    from gbulb import install
    import sys

    called = False

    def set_event_loop_policy(pol):
        nonlocal called
        called = True
        cls_name = pol.__class__.__name__
        if gtk:
            assert cls_name == 'GtkEventLoopPolicy'
        else:
            assert cls_name == 'GLibEventLoopPolicy'

    if gtk and 'gbulb.gtk' in sys.modules:
        del sys.modules['gbulb.gtk']

    mock_repository = mock.Mock()
    if not gtk_available:
        del mock_repository.Gtk

    with mock.patch.dict('sys.modules', {'gi.repository': mock_repository}):
        with mock.patch('asyncio.set_event_loop_policy', set_event_loop_policy):
            import_error = gtk and not gtk_available
            try:
                install(gtk=gtk)
            except ImportError:
                assert import_error
            else:
                assert not import_error
                assert called


def test_get_event_loop():
    import asyncio
    import gbulb

    assert asyncio.get_event_loop() is gbulb.get_event_loop()


def test_wait_signal(glib_loop):
    import asyncio
    from gi.repository import GObject
    from gbulb import wait_signal

    class TestObject(GObject.GObject):
        __gsignals__ = {
            'foo': (GObject.SIGNAL_RUN_LAST, None, (str,)),
        }

    t = TestObject()

    def emitter():
        yield
        t.emit('foo', 'frozen brains tell no tales')

    called = False
    @asyncio.coroutine
    def waiter():
        nonlocal called
        r = yield from wait_signal(t, 'foo', loop=glib_loop)
        assert r == (t, 'frozen brains tell no tales')
        called = True

    glib_loop.run_until_complete(asyncio.wait([waiter(), emitter()], timeout=1, loop=glib_loop))

    assert called


def test_wait_signal_cancel(glib_loop):
    import asyncio
    from gi.repository import GObject
    from gbulb import wait_signal

    class TestObject(GObject.GObject):
        __gsignals__ = {
            'foo': (GObject.SIGNAL_RUN_LAST, None, (str,)),
        }

    t = TestObject()

    def emitter():
        yield
        t.emit('foo', 'frozen brains tell no tales')

    called = False
    cancelled = False
    def waiter():
        nonlocal cancelled
        yield

        r = wait_signal(t, 'foo', loop=glib_loop)
        @r.add_done_callback
        def caller(r):
            nonlocal called
            called = True

        r.cancel()
        assert r.cancelled()
        cancelled = True

    glib_loop.run_until_complete(asyncio.wait([waiter(), emitter()], timeout=1, loop=glib_loop))

    assert cancelled
    assert called


def test_wait_signal_cancel_state():
    from gbulb import wait_signal
    m = wait_signal(mock.Mock(), 'anything')
    assert m.cancel()
    assert not m.cancel()
