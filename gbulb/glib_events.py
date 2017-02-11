"""PEP 3156 event loop based on GLib"""

import asyncio
import os
import signal
import socket
import sys
import threading
from asyncio import base_events, events, futures, sslproto, tasks


from gi.repository import GLib, Gio

from . import transports

__all__ = ['GLibEventLoop', 'GLibEventLoopPolicy']


# The Windows `asyncio` implementation doesn't actually use this, but
# `glib` abstracts so nicely over this that we can use it on any platform
if sys.platform == "win32":
    class AbstractChildWatcher:
        pass
else:
    from asyncio.unix_events import AbstractChildWatcher

class GLibChildWatcher(AbstractChildWatcher):
    def __init__(self):
        self._sources = {}

    def attach_loop(self, loop):
        # just ignored
        pass

    def add_child_handler(self, pid, callback, *args):
        self.remove_child_handler(pid)

        source = GLib.child_watch_add(0, pid, self.__callback__)
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

    def __callback__(self, pid, status):

        try:
            source, callback, args = self._sources.pop(pid)
        except KeyError:
            return

        GLib.source_remove(source)

        if hasattr(os, "WIFSIGNALED") and os.WIFSIGNALED(status):
            returncode = -os.WTERMSIG(status)
        elif hasattr(os, "WIFEXITED") and os.WIFEXITED(status):
            returncode = os.WEXITSTATUS(status)

            #FIXME: Hack for adjusting invalid status returned by GLIB
            #    Looks like there is a bug in glib or in pygobject
            if returncode > 128:
                returncode = 128 - returncode
        else:
            returncode = status

        callback(pid, returncode, *args)



class GLibHandle(events.Handle):
    __slots__ = ('_source', '_repeat')

    def __init__(self, *, loop, source, repeat, callback, args):
        super().__init__(callback, args, loop)

        self._source = source
        self._repeat = repeat
        loop._handlers.add(self)
        source.set_callback(self.__callback__, self)
        source.attach(loop._context)

    def cancel(self):
        super().cancel()
        self._source.destroy()
        self._loop._handlers.discard(self)

    def __callback__(self, ignore_self):
        # __callback__ is called within the MainContext object, which is
        # important in case that code includes a `Gtk.main()` or some such.
        # Otherwise what happens is the loop is started recursively, but the
        # callbacks don't finish firing, so they can't be rescheduled.
        self._run()
        if not self._repeat:
            self._source.destroy()
            self._loop._handlers.discard(self)

        return self._repeat


class GLibBaseEventLoop(base_events.BaseEventLoop):
    def __init__(self, context=None):
        self._handlers = set()
        
        self._accept_futures = {}
        self._context = context or GLib.MainContext()
        self._selector = self
        self._sighandlers = {}
        
        super().__init__()
    
    def close(self):
        for future in self._accept_futures.values():
            future.cancel()
        self._accept_futures.clear()
        
        for s in list(self._handlers):
            s.cancel()
        self._handlers.clear()
        
        for sig in list(self._sighandlers):
            self.remove_signal_handler(sig)
        
        super().close()

    def select(self, timeout=None):
        self._context.acquire()
        try:
            if timeout is None:
                self._context.iteration(True)
            elif timeout <= 0:
                self._context.iteration(False)
            else:
                # Schedule fake callback that will trigger an event and cause the loop to terminate
                # after the given number of seconds
                handle = GLibHandle(
                        loop=self,
                        source=GLib.Timeout(timeout*1000),
                        repeat=False,
                        callback=lambda: None,
                        args=())
                try:
                    self._context.iteration(True)
                finally:
                    handle.cancel()
            return ()  # Available events are dispatched immediately and not returned
        finally:
            self._context.release()



    def _make_socket_transport(self, sock, protocol, waiter=None, *,
                               extra=None, server=None):
        """Create socket transport."""
        return transports.SocketTransport(self, sock, protocol, waiter, extra, server)

    def _make_ssl_transport(self, rawsock, protocol, sslcontext, waiter=None,
                            *, server_side=False, server_hostname=None,
                            extra=None, server=None):
        """Create SSL transport."""
        if not sslproto._is_sslproto_available():
            raise NotImplementedError("Proactor event loop requires Python 3.5"
                                      " or newer (ssl.MemoryBIO) to support "
                                      "SSL")

        ssl_protocol = sslproto.SSLProtocol(self, protocol, sslcontext, waiter,
                                            server_side, server_hostname)
        transports.SocketTransport(self, rawsock, ssl_protocol, extra=extra, server=server)
        return ssl_protocol._app_transport

    def _make_datagram_transport(self, sock, protocol,
                                 address=None, waiter=None, extra=None):
        """Create datagram transport."""
        raise NotImplementedError

    def _make_read_pipe_transport(self, pipe, protocol, waiter=None,
                                  extra=None):
        """Create read pipe transport."""
        raise NotImplementedError

    def _make_write_pipe_transport(self, pipe, protocol, waiter=None,
                                   extra=None):
        """Create write pipe transport."""
        raise NotImplementedError

    @asyncio.coroutine
    def _make_subprocess_transport(self, protocol, args, shell,
                                   stdin, stdout, stderr, bufsize,
                                   extra=None, **kwargs):
        """Create subprocess transport."""
        raise NotImplementedError

    def _write_to_self(self):
        self._context.wakeup()

    def _process_events(self, event_list):
        """Process selector events."""
        pass  # This is already done in `.select()`

    def _start_serving(self, protocol_factory, sock,
                       sslcontext=None, server=None, backlog=100):

        def server_loop(f=None):
            try:
                if f is not None:
                    (conn, addr) = f.result()
                    protocol = protocol_factory()
                    if sslcontext is not None:
                        self._make_ssl_transport(
                            conn, protocol, sslcontext, server_side=True,
                            extra={'peername': addr}, server=server)
                    else:
                        self._make_socket_transport(
                            conn, protocol,
                            extra={'peername': addr}, server=server)
                if self.is_closed():
                    return
                f = self.sock_accept(sock)
            except OSError as exc:
                if sock.fileno() != -1:
                    self.call_exception_handler({
                        'message': 'Accept failed on a socket',
                        'exception': exc,
                        'socket': sock,
                    })
                    sock.close()
            except futures.CancelledError:
                sock.close()
            else:
                self._accept_futures[sock.fileno()] = f
                f.add_done_callback(server_loop)

        self.call_soon(server_loop)

    def _stop_serving(self, sock):
        if sock.fileno() in self._accept_futures:
            self._accept_futures[sock.fileno()].cancel()
        sock.close()




    def _check_not_coroutine(self, callback, name):
        """Check whether the given callback is a coroutine or not."""
        from asyncio import coroutines
        if (coroutines.iscoroutine(callback) or
                coroutines.iscoroutinefunction(callback)):
            raise TypeError("coroutines cannot be used with {}()".format(name))

    def _channel_from_socket(self, sock):
        """Create GLib IOChannel for the given socket object."""
        if not isinstance(sock, int):
            fd = sock.fileno()
        else:
            fd = sock
        
        if sys.platform == "win32":
            return GLib.IOChannel.win32_new_socket(fd)
        else:
            return GLib.IOChannel.unix_new(fd)

    def _delayed(self, source, callback=None, *args):
        """Create a future that will complete after the given GLib Source object has become ready
        and the data it tracks has been processed."""
        future = None
        def handle_ready(*args):
            try:
                if callback:
                    (done, result) = callback(*args)
                else:
                    (done, result) = (True, None)

                if done:
                    future.set_result(result)
                    future.handle.cancel()
            except Exception as error:
                if not future.cancelled():
                    future.set_exception(error)
                future.handle.cancel()

        # Create future and properly wire up it's cancellation with the
        # handle's cancellation machinery
        future = self.create_future()
        future.handle = GLibHandle(
            loop=self,
            source=source,
            repeat=True,
            callback=handle_ready,
            args=args
        )
        return future

    def _socket_handle_errors(self, sock):
        """Raise exceptions for error states (SOL_ERROR) on the given socket object."""
        errno = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if errno != 0:
            if sys.platform == "win32":
                msg = socket.errorTab.get(errno, "Error {0}".format(errno))
                raise OSError(errno, "[WinError {0}] {1}".format(errno, msg), None, errno)
            else:
                raise OSError(errno, os.strerror(errno))




    def sock_connect(self, sock, address):
        # Request connection on socket (it is expected that `sock` is already non-blocking)
        try:
            sock.connect(address)
        except BlockingIOError:
            pass

        # Create glib IOChannel for socket and wait for it to become writable
        channel = self._channel_from_socket(sock)
        source = GLib.io_create_watch(channel, GLib.IO_OUT)
        def sock_finish_connect(sock):
            self._socket_handle_errors(sock)
            return (True, sock)
        return self._delayed(source, sock_finish_connect, sock)

    def sock_accept(self, sock):
        channel = self._channel_from_socket(sock)
        source = GLib.io_create_watch(channel, GLib.IO_IN)
        def sock_connection_received(sock):
            return (True, sock.accept())

        @asyncio.coroutine
        def accept_coro(future, conn):
            # Coroutine closing the accept socket if the future is cancelled
            try:
                return (yield from future)
            except futures.CancelledError:
                sock.close()
                raise

        future = self._delayed(source, sock_connection_received, sock)
        return self.create_task(accept_coro(future, sock))

    def sock_recv(self, sock, nbytes, flags=0):
        channel = self._channel_from_socket(sock)
        source = GLib.io_create_watch(channel, GLib.IO_IN | GLib.IO_HUP)
        def sock_data_received(sock, nbytes, flags):
            return (True, sock.recv(nbytes, flags))
        return self._delayed(source, sock_data_received, sock, nbytes, flags)

    def sock_sendall(self, sock, buf, flags=0):
        buflen = len(buf)
        
        # Fast-path: If there is enough room in the OS buffer all data can be written synchronously
        try:
            nbytes = sock.send(buf, flags)
        except BlockingIOError:
            nbytes = 0
        else:
            if nbytes >= len(buf):
                # All data was written synchronously in one go
                result = self.create_future()
                result.set_result(nbytes)
                return result
        
        # Chop off the initially transmitted data and store result
        # as a bytearray for easier future modification
        buf = bytearray(buf[nbytes:])
        
        # Send the remaining data asynchronously as the socket becomes writable
        channel = self._channel_from_socket(sock)
        source = GLib.io_create_watch(channel, GLib.IO_OUT)
        def sock_writable(buflen, sock, buf, flags):
            nbytes = sock.send(buf, flags)
            if nbytes >= len(buf):
                return (True, buflen)
            else:
                del buf[0:nbytes]
                return (False, buflen)
        return self._delayed(source, sock_writable, buflen, sock, buf, flags)
    
    
    if sys.platform != "win32":
        def add_signal_handler(self, sig, callback, *args):
            self.remove_signal_handler(sig)
            
            s = GLib.unix_signal_source_new(sig)
            if s is None:
                # Show custom error messages for signal that are uncatchable
                if sig == signal.SIGKILL:
                    raise RuntimeError("cannot catch SIGKILL")
                elif sig == signal.SIGSTOP:
                    raise RuntimeError("cannot catch SIGSTOP")
                else:
                    raise ValueError("signal not supported")
            
            assert sig not in self._sighandlers
            
            self._sighandlers[sig] = GLibHandle(
                loop=self,
                source=s,
                repeat=True,
                callback=callback,
                args=args)
        
        def remove_signal_handler(self, sig):
            try:
                self._sighandlers.pop(sig).cancel()
                return True
            except KeyError:
                return False



class GLibEventLoop(GLibBaseEventLoop):
    def __init__(self, *, context=None, application=None):
        self._application = application
        self._running = False

        super().__init__(context)
        if application is None:
            self._mainloop = GLib.MainLoop(self._context)

    def is_running(self):
        return self._running

    def run(self):
        recursive = self.is_running()
        if not recursive and hasattr(events, "_get_running_loop") and events._get_running_loop():
            raise RuntimeError(
                'Cannot run the event loop while another loop is running')

        if not recursive:
            self._running = True
            if hasattr(events, "_set_running_loop"):
                events._set_running_loop(self)

        try:
            if self._application is not None:
                self._application.run(None)
            else:
                self._mainloop.run()
        finally:
            if not recursive:
                self._running = False
                if hasattr(events, "_set_running_loop"):
                    events._set_running_loop(None)

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

    def run_forever(self, application=None):
        """Run the event loop until stop() is called."""
        if application is not None:
            self.set_application(application)
        
        if self.is_running():
            raise RuntimeError(
                "Recursively calling run_forever is forbidden. "
                "To recursively run the event loop, call run().")

        try:
            self.run()
        finally:
            self.stop()

    # Methods scheduling callbacks.  All these return Handles.
    def call_soon(self, callback, *args):
        self._check_not_coroutine(callback, 'call_soon')
        source = GLib.Idle()

        # XXX: we set the source's priority to high for the following scenario:
        #
        # - loop.sock_connect() begins asynchronous connection
        # - this adds a write callback to detect when the connection has
        #   completed
        # - this write callback sets the result of a future
        # - future.Future schedules callbacks with call_later.
        # - the callback for this future removes the write callback
        # - GLib.Idle() has a much lower priority than that of the GSource for
        #   the writer, so it never gets scheduled.
        source.set_priority(GLib.PRIORITY_HIGH)

        return GLibHandle(
            loop=self,
            source=source,
            repeat=False,
            callback=callback,
            args=args)

    call_soon_threadsafe = call_soon

    def call_later(self, delay, callback, *args):
        self._check_not_coroutine(callback, 'call_later')

        return GLibHandle(
            loop=self,
            source=GLib.Timeout(delay*1000) if delay > 0 else GLib.Idle(),
            repeat=False,
            callback=callback,
            args=args)

    def call_at(self, when, callback, *args):
        self._check_not_coroutine(callback, 'call_at')

        return self.call_later(when - self.time(), callback, *args)

    def time(self):
        return GLib.get_monotonic_time() / 1000000

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
        self._watcher_lock = threading.Lock()

        self._watcher = None
        self._policy = asyncio.DefaultEventLoopPolicy()
        self._policy.new_event_loop = self.new_event_loop
        self.get_event_loop = self._policy.get_event_loop
        self.set_event_loop = self._policy.set_event_loop

    def get_child_watcher(self):
        if self._watcher is None:
            with self._watcher_lock:
                if self._watcher is None:
                    self._watcher = GLibChildWatcher()
        return self._watcher

    def set_child_watcher(self, watcher):
        """Set a child watcher.

        Must be an an instance of GLibChildWatcher, as it ties in with GLib
        appropriately.
        """

        if watcher is not None and not isinstance(watcher, GLibChildWatcher):
            raise TypeError("Only GLibChildWatcher is supported!")

        with self._watcher_lock:
            self._watcher = watcher

    def new_event_loop(self):
        """Create a new event loop and return it."""
        if not self._default_loop and isinstance(threading.current_thread(), threading._MainThread):
            l = self.get_default_loop()
        else:
            #l = GLibEventLoop()
            l = GLibBaseEventLoop()
        l._policy = self

        return l

    def get_default_loop(self):
        """Get the default event loop."""
        if not self._default_loop:
            self._default_loop = self._new_default_loop()
        return self._default_loop

    def _new_default_loop(self):
        #l = GLibEventLoop(
        #    context=GLib.main_context_default(), application=self._application)
        l = GLibBaseEventLoop(context=GLib.main_context_default())
        l._policy = self
        return l
