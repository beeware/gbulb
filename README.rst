.. |pyversions| image:: https://img.shields.io/pypi/pyversions/gbulb.svg
   :target: https://pypi.python.org/pypi/gbulb
   :alt: Python Versions

.. |version| image:: https://img.shields.io/pypi/v/gbulb.svg
   :target: https://pypi.python.org/pypi/gbulb
   :alt: PyPI Version

.. |maturity| image:: https://img.shields.io/pypi/status/gbulb.svg
   :target: https://pypi.python.org/pypi/gbulb
   :alt: Maturity

.. |license| image:: https://img.shields.io/pypi/l/gbulb.svg
   :target: https://github.com/beeware/gbulb/blob/main/LICENSE
   :alt: BSD License

.. |ci| image:: https://github.com/beeware/gbulb/workflows/CI/badge.svg?branch=main
   :target: https://github.com/beeware/gbulb/actions
   :alt: Build Status

.. |social| image:: https://img.shields.io/discord/836455665257021440?label=Discord%20Chat&logo=discord&style=plastic
   :target: https://beeware.org/bee/chat/
   :alt: Discord server

gbulb
=====

|pyversions| |version| |maturity| |license| |ci| |social|

Gbulb is a Python library that implements a `PEP 3156
<http://www.python.org/dev/peps/pep-3156/>`__ interface for the `GLib main event
loop <https://developer.gnome.org/glib/stable/glib-The-Main-Event-Loop.html>`__
under UNIX-like systems.

As much as possible, except where noted below, it mimics asyncio's interface.
If you notice any differences, please report them.

Requirements
------------

- python 3.8+
- pygobject
- glib
- gtk+3 (optional)

Usage
-----

GLib event loop
~~~~~~~~~~~~~~~

Example usage::

    import asyncio, gbulb
    gbulb.install()
    asyncio.get_event_loop().run_forever()

Gtk+ event loop *(suitable for GTK+ applications)*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example usage::

    import asyncio, gbulb
    gbulb.install(gtk=True)
    asyncio.get_event_loop().run_forever()

GApplication/GtkApplication event loop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example usage::

    import asyncio, gbulb
    gbulb.install(gtk=True)  # only necessary if you're using GtkApplication

    loop = asyncio.get_event_loop()
    loop.run_forever(application=my_gapplication_object)

Waiting on a signal asynchronously
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See examples/wait_signal.py

Known issues
------------

- Windows is not supported, sorry. If you are interested in this, please help
  me get it working! I don't have Windows so I can't test it.

Divergences with PEP 3156
-------------------------

In GLib, the concept of event loop is split in two classes: GLib.MainContext
and GLib.MainLoop.

The event loop is mostly implemented by MainContext. MainLoop is just a wrapper
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

- ``.run_forever()`` and ``.run_until_complete()`` are not guaranteed to run
  immediately. If the context is owned by another thread, then they will
  block until the context is released by the other thread.

- ``.stop()`` is relevant only when the currently running Glib.MainLoop object
  was created by this asyncio object (i.e. by calling ``.run_forever()`` or
  ``.run_until_complete()``). The event loop will quit only when it regains
  control of the context. This can happen in two cases:

  1. when multiple event loop are enclosed (by creating new ``MainLoop``
     objects and calling ``.run()`` recursively)
  2. when the event loop has not even yet started because it is still
     trying to acquire the context

It would be wiser not to use any recursion at all. ``GLibEventLoop`` will
actually prevent you from doing that (in accordance with PEP 3156), however
``GtkEventLoop`` will allow you to call ``run()`` recursively. You should also keep
in mind that enclosed loops may be started at any time by third-party code
calling GLib's primitives.

Testing
-------

Testing GBulb requires a Linux environment that has GLib and GTK development
libraries available.

The tests folder contains a Dockerfile that defines a complete testing
environment. To use the Docker environment, run the following from the root of
the git checkout:

   $ docker buildx build --tag beeware/gbulb:latest --file ./tests/Dockerfile .
   $ docker run --rm --volume $(PWD):/home/brutus/gbulb:z -it beeware/gbulb:latest

This will drop you into an Ubuntu 24.04 shell that has Python 3.8-3.13
installed, mounting the current working directory as `/home/brutus/gbulb`. You
can use this to create virtual environments for each Python version.

Once you have an active virtual environment, run:

   (venv) $ pip install -e .[dev]
   (venv) $ pytest

to run the test suite. Alternatively, you can install tox, and then run:

   # To test a single Python version
   (venv) $ tox -e py

   # To test Python 3.10 specifically
   (venv) $ tox -e py310

   # To test all versions
   (venv) $ tox

Community
---------

gbulb is part of the `BeeWare suite`_. You can talk to the community through:

* `@pybeeware on Twitter <https://twitter.com/pybeeware>`__

* `Discord <https://beeware.org/bee/chat/>`__

* The gbulb `Github Discussions forum <https://github.com/beeware/gbulb/discussions>`__

We foster a welcoming and respectful community as described in our
`BeeWare Community Code of Conduct`_.

Contributing
------------

If you experience problems with gbulb, `log them on GitHub`_. If you
want to contribute code, please `fork the code`_ and `submit a pull request`_.

.. _BeeWare suite: http://beeware.org
.. _BeeWare Community Code of Conduct: http://beeware.org/community/behavior/
.. _log them on Github: https://github.com/beeware/gbulb/issues
.. _fork the code: https://github.com/beeware/gbulb
.. _submit a pull request: https://github.com/beeware/gbulb/pulls
