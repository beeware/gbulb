import asyncio
import sys

import pytest

from unittest import mock, skipIf
from gi.repository import Gio, GLib

from utils import glib_loop, glib_policy

is_windows = (sys.platform == "win32")


class TestGLibEventLoopPolicy:
    def test_set_child_watcher(self, glib_policy):
        from gbulb.glib_events import GLibChildWatcher
        with pytest.raises(TypeError):
            glib_policy.set_child_watcher(5)

        glib_policy.set_child_watcher(None)
        assert isinstance(glib_policy.get_child_watcher(), GLibChildWatcher)

        g = GLibChildWatcher()
        glib_policy.set_child_watcher(g)

        assert glib_policy.get_child_watcher() is g

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
        call_manager = mock.Mock()

        from gbulb.glib_events import GLibHandle

        # stub this out, we don't care if it gets called or not
        call_manager.loop.get_debug = lambda: True

        h = GLibHandle(
            loop=call_manager.loop,
            source=call_manager.source,
            repeat=True,
            callback=call_manager.callback,
            args=(),
        )

        print(call_manager.mock_calls)

        expected_calls = [
            mock.call.loop._handlers.add(h),
            mock.call.source.set_callback(h.__callback__, h),
            mock.call.source.attach(call_manager.loop._context),
        ]

        assert call_manager.mock_calls == expected_calls


@asyncio.coroutine
def no_op_coro():
    pass


class TestBaseGLibEventLoop:
    @skipIf(is_windows, "Unix signal handlers are not supported on Windows")
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

    @skipIf(is_windows, "Unix signal handlers are not supported on Windows")
    def test_remove_signal_handler(self, glib_loop):
        import signal

        glib_loop.add_signal_handler(signal.SIGHUP, None)

        assert signal.SIGHUP in glib_loop._sighandlers
        assert glib_loop.remove_signal_handler(signal.SIGHUP)
        assert signal.SIGHUP not in glib_loop._sighandlers

        # FIXME: it'd be great if we could actually try signalling the process

    @skipIf(is_windows, "Unix signal handlers are not supported on Windows")
    def test_remove_signal_handler_unhandled(self, glib_loop):
        import signal
        assert not glib_loop.remove_signal_handler(signal.SIGHUP)

    @skipIf(is_windows, "Unix signal handlers are not supported on Windows")
    def test_remove_signal_handler_sigkill(self, glib_loop):
        import signal
        with pytest.raises(RuntimeError):
            glib_loop.add_signal_handler(signal.SIGKILL, None)

    @skipIf(is_windows, "Unix signal handlers are not supported on Windows")
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

    @skipIf(is_windows, "Waiting on raw file descriptors only works for sockets on Windows")
    def test_add_writer(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        called = False

        def callback(*args):
            nonlocal called
            called = True
            glib_loop.stop()

        glib_loop.add_writer(wfd, callback)
        glib_loop.run_forever()
        os.close(rfd)
        os.close(wfd)

        assert called, 'callback handler didnt fire'

    @skipIf(is_windows, "Waiting on raw file descriptors only works for sockets on Windows")
    def test_add_reader(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        called = False

        def callback(*args):
            nonlocal called
            called = True
            glib_loop.stop()

        glib_loop.add_reader(rfd, callback)

        os.write(wfd, b'hey')

        glib_loop.run_forever()

        os.close(rfd)
        os.close(wfd)

        assert called, 'callback handler didnt fire'

    @skipIf(is_windows, "Waiting on raw file descriptors only works for sockets on Windows")
    def test_add_reader_file(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        f = os.fdopen(rfd, 'r')

        glib_loop.add_reader(f, None)

        os.close(rfd)
        os.close(wfd)

    @skipIf(is_windows, "Waiting on raw file descriptors only works for sockets on Windows")
    def test_add_writer_file(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        f = os.fdopen(wfd, 'r')

        glib_loop.add_writer(f, None)

        os.close(rfd)
        os.close(wfd)

    @skipIf(is_windows, "Waiting on raw file descriptors only works for sockets on Windows")
    def test_remove_reader(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        f = os.fdopen(wfd, 'r')

        glib_loop.add_reader(f, None)

        os.close(rfd)
        os.close(wfd)

        assert glib_loop.remove_reader(f)
        assert not glib_loop.remove_reader(f.fileno())

    @skipIf(is_windows, "Waiting on raw file descriptors only works for sockets on Windows")
    def test_remove_writer(self, glib_loop):
        import os
        rfd, wfd = os.pipe()

        f = os.fdopen(wfd, 'r')

        glib_loop.add_writer(f, None)

        os.close(rfd)
        os.close(wfd)

        assert glib_loop.remove_writer(f)
        assert not glib_loop.remove_writer(f.fileno())

    def test_time(self, glib_loop):
        import time
        SLEEP_TIME = .125
        s = glib_loop.time()
        time.sleep(SLEEP_TIME)
        e = glib_loop.time()

        diff = e - s
        assert SLEEP_TIME + .005 >= diff >= SLEEP_TIME

    def test_call_at(self, glib_loop):
        called = False

        def handler():
            nonlocal called
            called = True

            now = glib_loop.time()
            glib_loop.stop()

            print(now, s)

            assert now - s <= 0.2

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
        h = glib_loop.call_soon(lambda: None)
        assert h._source.get_priority() == GLib.PRIORITY_DEFAULT
        h.cancel()

    @skipIf(is_windows, "Waiting on raw file descriptors only works for sockets on Windows")
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


@skipIf(is_windows, "Unix signal handlers are not supported on Windows")
def test_signal_handling_with_multiple_invocations(glib_loop):
    import os
    import signal

    glib_loop.call_later(0.01, os.kill, os.getpid(), signal.SIGINT)

    with pytest.raises(KeyboardInterrupt):
        glib_loop.run_forever()

    glib_loop.run_until_complete(asyncio.sleep(0))


@skipIf(is_windows, "Unix signal handlers are not supported on Windows")
def test_default_signal_handling(glib_loop):
    import os
    import signal

    glib_loop.call_later(0.01, os.kill, os.getpid(), signal.SIGINT)

    with pytest.raises(KeyboardInterrupt):
        glib_loop.run_forever()


def test_subprocesses_read_after_closure(glib_loop):
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

        yield from proc.wait()

    glib_loop.run_until_complete(coro())


def test_subprocesses_readline_without_closure(glib_loop):
    # needed to ensure events.get_child_watcher() returns the right object
    import gbulb
    gbulb.install()

    @asyncio.coroutine
    def run():
        proc = yield from asyncio.create_subprocess_exec(
            'cat', stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, loop=glib_loop)

        try:
            proc.stdin.write(b'test line\n')
            yield from proc.stdin.drain()

            line = yield from asyncio.wait_for(
                proc.stdout.readline(), timeout=5, loop=glib_loop)
            assert line == b'test line\n'

            proc.stdin.close()

            line = yield from asyncio.wait_for(
                proc.stdout.readline(), timeout=5, loop=glib_loop)
            assert line == b''
        finally:
            yield from proc.wait()

    glib_loop.run_until_complete(run())


def test_sockets(glib_loop):
    server_done = asyncio.Event(loop=glib_loop)
    server_success = False

    @asyncio.coroutine
    def cb(reader, writer):
        nonlocal server_success

        writer.write(b'cool data\n')
        yield from writer.drain()

        print('reading')
        d = yield from reader.readline()
        print('hrm', d)
        server_success = d == b'thank you\n'

        writer.close()
        server_done.set()

    @asyncio.coroutine
    def run():
        s = yield from asyncio.start_server(cb, '127.0.0.1', 0, loop=glib_loop)
        reader, writer = yield from asyncio.open_connection('127.0.0.1', s.sockets[0].getsockname()[-1], loop=glib_loop)

        d = yield from reader.readline()
        assert d == b'cool data\n'

        writer.write(b'thank you\n')
        yield from writer.drain()

        writer.close()

        yield from server_done.wait()

        assert server_success

    glib_loop.run_until_complete(run())
