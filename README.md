# gbulb - a PEP 3156 event loop based on GLib


Gbulb is a python library that implements a [PEP 3156][PEP3156] interface for
the [GLib main event loop][glibloop]. It is designed to be used together with
the [tulip reference implementation][tulip].

This is a **work in progress**. The code is experimental and may break at any
time.


Anthony Baire

## Licence

Apache 2.0

## Requirements
- python3.3
- tulip
- glib 
- gtk+3
- pygobject

## Usage

### GLib event loop

        import asyncio, gbulb
        asyncio.set_event_loop_policy(gbulb.GLibEventLoopPolicy())

### Gtk+ event loop *(suitable for GTK+ applications)*

        import asyncio, gbulb
        asyncio.set_event_loop_policy(gbulb.GtkEventLoopPolicy())

## Known issues

- subprocesses can only be started from the default context (usually the one
  used by the main thread)

## Divergences with PEP 3156

In GLib, the concept of event loop is split in two classes: GLib.MainContext
and GLib.MainLoop.

The thing is mostly implemented by MainContext. MainLoop is just a wrapper
that implements the run() and quit() functions. MainLoop.run() atomically
acquires a MainContext and repeatedly calls MainContext.iteration() until
MainLoop.quit() is called.

A MainContext is not bound to a particular thread, however is cannot be used
by multiple threads concurrently. If the context is owned by another thread,
then MainLoop.run() will block until the context is released by the other
thread.

MainLoop.run() may be called recursively by the same thread (this is mainly
used for implementing modal dialogs in Gtk).


The issue: given a context, GLib provides no ways to know if there is an
existing event loop running for that context. It implies the following
divergences with PEP 3156:

 - .run_forever() and .run_until_complete() are not guaranteed to run
   immediatly. If the context is owned by another thread, then they will
   block until the context is released by the other thread.

 - .stop() is relevant only when the currently running Glib.MainLoop object
   was created by this asyncio object (i.e. by calling .run_forever() or
   .run_until_complete()). The event loop will quit only when it regains
   control of the context. This can happen in two cases:
    1. when multiple event loop are enclosed (by creating new MainLoop
       objects and calling .run() recursively)
    2. when the event loop has not even yet started because it is still
       trying to acquire the context

It should be wiser not to use any recursion at all. GLibEventLoop will
actually prevent you from doing that (in accordance with PEP 3156). However
you should keep in mind that enclosed loops may be started at any time by
third-party code calling directly GLib's primitives.



[PEP3156]:  http://www.python.org/dev/peps/pep-3156/
[tulip]:    http://code.google.com/p/tulip/
[glibloop]: https://developer.gnome.org/glib/stable/glib-The-Main-Event-Loop.html
