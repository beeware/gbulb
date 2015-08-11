import asyncio

import gbulb

from gi.repository import Gtk


@asyncio.coroutine
def counter(label):
    i = 0
    while True:
        label.set_text(str(i))
        yield from asyncio.sleep(1)
        i += 1


@asyncio.coroutine
def text_watcher(label):
    while True:
        yield from gbulb.wait_signal(label, 'changed')
        print('label changed', label.get_text())


def main():
    gbulb.install(gtk=True)
    loop = gbulb.get_event_loop()

    display = Gtk.Entry()
    vbox = Gtk.VBox()

    vbox.pack_start(display, True, True, 0)

    win = Gtk.Window(title='Counter window')
    win.connect('delete-event', lambda *args: loop.stop())
    win.add(vbox)

    win.show_all()

    asyncio.async(text_watcher(display))
    asyncio.async(counter(display))
    loop.run_forever()

if __name__ == '__main__':
    main()
