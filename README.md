# gbulb - a PEP 3156 event loop based on GLib


Gbulb is a Python library that implements a [PEP 3156][PEP3156] interface for
the [GLib main event loop][glibloop] under UNIX-like systems.

The code needs to be thoroughly tested, it should be considered as unstable for
the moment.

Anthony Baire

## Licence

Apache 2.0

## Homepage

[https://bitbucket.org/a_ba/gbulb](https://bitbucket.org/a_ba/gbulb)

## Requirements
- python3.4 or python3.3+[asyncio][asyncio]
- pygobject
- glib 
- gtk+3 (optional)

## Usage

### GLib event loop

        import asyncio, gbulb
        asyncio.set_event_loop_policy(gbulb.GLibEventLoopPolicy())

### Gtk+ event loop *(suitable for GTK+ applications)*

        import asyncio, gbulb
        asyncio.set_event_loop_policy(gbulb.GtkEventLoopPolicy())

### GApplication/GtkApplication event loop

        import asyncio, gbulb
        asyncio.set_event_loop_policy(gbulb.GApplicationEventLoopPolicy())

        loop = asyncio.get_event_loop()
        loop.run_forever(application=my_gapplication_object)

## Known issues

- Windows is not supported, sorry. If you are interested in this, please help
  me get it working! I don't have Windows so I can't test it.

## Divergences with PEP 3156

In GLib, the concept of event loop is split in two classes: GLib.MainContext
and GLib.MainLoop.

The thing is mostly implemented by MainContext. MainLoop is just a wrapper
that implements the run() and quit() functions. MainLoop.run() atomically
acquires a MainContext and repeatedly calls MainContext.iteration() until
MainLoop.quit() is called.

A MainContext is not bound to a particular thread, however it cannot be used
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
[asyncio]:  https://pypi.python.org/pypi/asyncio
[glibloop]: https://developer.gnome.org/glib/stable/glib-The-Main-Event-Loop.html
