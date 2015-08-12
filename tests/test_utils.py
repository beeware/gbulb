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

    called = False

    def set_event_loop_policy(pol):
        nonlocal called
        called = True
        cls_name = pol.__class__.__name__
        if gtk:
            assert cls_name == 'GtkEventLoopPolicy'
        else:
            assert cls_name == 'GLibEventLoopPolicy'

    with mock.patch('gbulb.utils.gtk_available', return_value=gtk_available):
        with mock.patch('asyncio.set_event_loop_policy', set_event_loop_policy):
            try:
                install(gtk=gtk)
            except ValueError:
                assert gtk and not gtk_available
            else:
                assert called


def test_get_event_loop():
    import asyncio
    import gbulb

    assert asyncio.get_event_loop() is gbulb.get_event_loop()


def test_wait_signal():
    import asyncio
    from gi.repository import GObject
    from gbulb import wait_signal, install, get_event_loop
    install()

    class TestObject(GObject.GObject):
        __gsignals__ = {
            'foo': (GObject.SIGNAL_RUN_LAST, None, (str,)),
        }

    t = TestObject()

    l = get_event_loop()
    def emitter():
        yield
        t.emit('foo', 'frozen brains tell no tales')

    called = False
    @asyncio.coroutine
    def waiter():
        nonlocal called
        r = yield from wait_signal(t, 'foo')
        assert r == (t, 'frozen brains tell no tales')
        called = True

    l.run_until_complete(asyncio.wait([waiter(), emitter()], timeout=1))

    assert called


def test_wait_signal_cancel():
    import asyncio
    from gi.repository import GObject
    from gbulb import wait_signal, install, get_event_loop
    install()

    class TestObject(GObject.GObject):
        __gsignals__ = {
            'foo': (GObject.SIGNAL_RUN_LAST, None, (str,)),
        }

    t = TestObject()

    l = get_event_loop()
    def emitter():
        yield
        t.emit('foo', 'frozen brains tell no tales')

    called = False
    cancelled = False
    def waiter():
        nonlocal cancelled
        yield

        r = wait_signal(t, 'foo')
        @r.add_done_callback
        def caller(r):
            nonlocal called
            called = True

        r.cancel()
        assert r.cancelled()
        cancelled = True

    l.run_until_complete(asyncio.wait([waiter(), emitter()], timeout=1))

    assert cancelled
    assert called


def test_wait_signal_cancel_state():
    from gbulb import wait_signal
    m = wait_signal(mock.Mock(), 'anything')
    assert m.cancel()
    assert not m.cancel()
