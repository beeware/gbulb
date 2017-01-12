import asyncio

import pytest

from unittest import mock
from gi.repository import Gio

from utils import glib_loop, glib_policy


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


class TestGLibHandle:
    def test_attachment_order(self, glib_loop):
        def add(handle):
            glib_loop._context.iteration(True)
            assert handle not in glib_loop._handlers
            assert not handle._source.is_destroyed(), "GSource was completed prior to it being in the handlers set."

        with mock.patch.object(glib_loop, '_handlers', add=add) as _handlers:
            handle = glib_loop.call_soon(print)


@asyncio.coroutine
def no_op_coro():
    pass


class TestBaseGLibEventLoop:
    def test_add_signal_handler(self, glib_loop):
        import os
        import signal

        called = False

        def handler():
            nonlocal called
            called = True
            glib_loop.stop()

        glib_loop.add_signal_handler(signal.SIGHUP, handler)
        assert signal.SIGHUP in glib_loop._sighandlers

        glib_loop.call_later(0.01, os.kill, os.getpid(), signal.SIGHUP)
        glib_loop.run_forever()

        assert called, 'signal handler didnt fire'

    def test_remove_signal_handler(self, glib_loop):
        import signal

        glib_loop.add_signal_handler(signal.SIGHUP, None)

        assert signal.SIGHUP in glib_loop._sighandlers
        assert glib_loop.remove_signal_handler(signal.SIGHUP)
        assert signal.SIGHUP not in glib_loop._sighandlers

        # FIXME: it'd be great if we could actually try signalling the process

    def test_remove_signal_handler_unhandled(self, glib_loop):
        import signal
        assert not glib_loop.remove_signal_handler(signal.SIGHUP)

    def test_remove_signal_handler_sigkill(self, glib_loop):
        import signal
        with pytest.raises(RuntimeError):
            glib_loop.add_signal_handler(signal.SIGKILL, None)

    def test_remove_signal_handler_sigill(self, glib_loop):
        import signal
        with pytest.raises(ValueError):
            glib_loop.add_signal_handler(signal.SIGILL, None)

    def test_run_until_complete_early_stop(self, glib_loop):
        import asyncio

        @asyncio.coroutine
        def coro():
            glib_loop.call_soon(glib_loop.stop)
            yield from asyncio.sleep(5)

        with pytest.raises(RuntimeError):
            glib_loop.run_until_complete(coro())

    def test_add_writer(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        called = False

        def callback(*args):
            nonlocal called
            called = True
            glib_loop.stop()

        os.close(rfd)
        os.close(wfd)

        glib_loop.add_writer(wfd, callback)
        glib_loop.run_forever()

        assert called, 'callback handler didnt fire'

    def test_add_reader(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        called = False

        def callback(*args):
            nonlocal called
            called = True
            glib_loop.stop()

        os.close(rfd)
        os.close(wfd)

        glib_loop.add_reader(rfd, callback)
        glib_loop.run_forever()

        assert called, 'callback handler didnt fire'

    def test_add_reader_file(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        f = os.fdopen(rfd, 'r')

        os.close(rfd)
        os.close(wfd)

        glib_loop.add_reader(f, None)

    def test_add_writer_file(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        f = os.fdopen(wfd, 'r')

        os.close(rfd)
        os.close(wfd)

        glib_loop.add_writer(f, None)

    def test_remove_reader(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        f = os.fdopen(wfd, 'r')

        os.close(rfd)
        os.close(wfd)

        glib_loop.add_reader(f, None)

        assert glib_loop.remove_reader(f)
        assert not glib_loop.remove_reader(f.fileno())

    def test_remove_writer(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        f = os.fdopen(wfd, 'r')

        os.close(rfd)
        os.close(wfd)

        glib_loop.add_writer(f, None)

        assert glib_loop.remove_writer(f)
        assert not glib_loop.remove_writer(f.fileno())

    def test_time(self, glib_loop):
        import time
        SLEEP_TIME = .125
        s = glib_loop.time()
        time.sleep(SLEEP_TIME)
        e = glib_loop.time()

        diff = e - s
        assert SLEEP_TIME + .001 >= diff >= SLEEP_TIME

    def test_call_at(self, glib_loop):
        called = False

        def handler():
            nonlocal called
            called = True

            now = glib_loop.time()
            glib_loop.stop()

            print(now, s)
            import math
            assert math.isclose(now, s, abs_tol=0.1)

        s = glib_loop.time()

        glib_loop.call_at(s+0.1, handler)
        glib_loop.run_forever()

        assert called, 'call_at handler didnt fire'

    def test_call_soon_no_coroutine(self, glib_loop):
        with pytest.raises(TypeError):
            glib_loop.call_soon(no_op_coro)

    def test_call_later_no_coroutine(self, glib_loop):
        with pytest.raises(TypeError):
            glib_loop.call_later(1, no_op_coro)

    def test_call_at_no_coroutine(self, glib_loop):
        with pytest.raises(TypeError):
            glib_loop.call_at(1, no_op_coro)

    def test_call_soon_priority_order(self, glib_loop):
        items = []

        def handler(i):
            items.append(i)

        for i in range(10):
            glib_loop.call_soon(handler, i)
        glib_loop.call_soon(glib_loop.stop)

        glib_loop.run_forever()

        assert items
        assert items == sorted(items)

    def test_call_soon_priority(self, glib_loop):
        def remover(fd):
            nonlocal removed
            assert glib_loop.remove_writer(fd)

            removed = True
            glib_loop.stop()

        def callback(fut):
            fut.set_result(None)

        def timeout():
            nonlocal timeout_occurred
            timeout_occurred = True
            glib_loop.stop()

        def run_test(fd):
            import asyncio
            from gi.repository import GLib

            fut = asyncio.Future(loop=glib_loop)
            fut.add_done_callback(lambda r: remover(fd))
            glib_loop.add_writer(fd, callback, fut)
            glib_loop.call_later(0.1, timeout)
            glib_loop.run_forever()

            assert not timeout_occurred
            assert removed

        import os
        rfd, wfd = os.pipe()

        removed = False
        timeout_occurred = False

        try:
            run_test(wfd)
        finally:
            os.close(rfd)
            os.close(wfd)

    def test_add_writer_multiple_calls(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        timeout_occurred = False

        expected_i = 10
        i = 0

        def callback():
            nonlocal i
            i += 1

            if i == expected_i:
                glib_loop.stop()

        def timeout():
            nonlocal timeout_occurred
            timeout_occurred = True
            glib_loop.stop()

        try:
            glib_loop.add_writer(wfd, callback)
            glib_loop.call_later(0.1, timeout)
            glib_loop.run_forever()
        finally:
            os.close(rfd)
            os.close(wfd)

        assert not timeout_occurred
        assert i == expected_i

    def test_call_soon_threadsafe(self, glib_loop):
        called = False

        def handler():
            nonlocal called
            called = True
            glib_loop.stop()

        glib_loop.call_soon_threadsafe(handler)
        glib_loop.run_forever()

        assert called, 'call_soon_threadsafe handler didnt fire'


class TestGLibEventLoop:
    def test_run_forever_recursion(self, glib_loop):
        def play_it_again_sam():
            with pytest.raises(RuntimeError):
                glib_loop.run_forever()

        h = glib_loop.call_soon(play_it_again_sam)
        glib_loop.call_soon(glib_loop.stop)
        glib_loop.run_forever()

    def test_run_recursion(self, glib_loop):
        passed = False
        def first():
            assert glib_loop._running

            glib_loop.call_soon(second)
            glib_loop.run()

            assert glib_loop._running

        def second():
            nonlocal passed
            assert glib_loop._running

            glib_loop.stop()

            assert glib_loop._running

            passed = True

        assert not glib_loop._running

        glib_loop.call_soon(first)
        glib_loop.run()

        assert not glib_loop._running
        assert passed

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


def test_default_signal_handling(glib_loop):
    import os
    import signal

    glib_loop.call_later(0.01, os.kill, os.getpid(), signal.SIGINT)

    with pytest.raises(KeyboardInterrupt):
        glib_loop.run_forever()


def test_subprocesses(glib_loop):
    import asyncio
    import subprocess

    # needed to ensure events.get_child_watcher() returns the right object
    import gbulb
    gbulb.install()

    @asyncio.coroutine
    def coro():
        proc = yield from asyncio.create_subprocess_exec(
            'cat', stdout=subprocess.PIPE, stdin=subprocess.PIPE,
            stderr=subprocess.PIPE, loop=glib_loop)

        proc.stdin.write(b'hey\n')
        yield from proc.stdin.drain()

        proc.stdin.close()

        out = yield from proc.stdout.read()
        assert out == b'hey\n'

    glib_loop.run_until_complete(coro())
