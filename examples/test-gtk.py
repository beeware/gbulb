#!/usr/bin/env python3
from gi.repository import Gtk, GObject
import asyncio
import gbulb

class ProgressBarWindow(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="ProgressBar Demo")
        self.set_border_width(10)

        vbox = Gtk.VBox()
        self.add(vbox)

        self.progressbar = Gtk.ProgressBar()
        vbox.pack_start(self.progressbar, True, True, 0)

        button = Gtk.Button("Magic button")
        button.connect("clicked", self.on_magic)
        vbox.pack_start(button, True, True, 0)
        self._magic_button = button

        button = Gtk.Button("Stop button")
        button.connect("clicked", self.on_stop)
        vbox.pack_start(button, True, True, 0)
        self._stop_button = button

        self._running = False

    def on_show_text_toggled(self, button):
        self.progressbar.set_text(text)
        self.progressbar.set_show_text(show_text)

    def on_activity_mode_toggled(self, button):
        self.progressbar.set_fraction(0.0)

    def on_right_to_left_toggled(self, button):
        value = button.get_active()
        self.progressbar.set_inverted(value)

    def on_magic(self, button):
        def coro():
            try:
                yield from gbulb.wait_signal(self._magic_button, "clicked")
                self.progressbar.set_text ("blah blah!")
                self.progressbar.set_fraction(0.50)

                r = yield from asyncio.sleep(1)

                self.progressbar.set_fraction(0.75)
                self.progressbar.set_text ("pouet pouet!")

                r = yield from gbulb.wait_signal(self._magic_button, "clicked")

                self.progressbar.set_fraction(1.0)
                self.progressbar.set_text ("done!")

                yield from asyncio.sleep(1)

            finally:
                self.progressbar.set_fraction(0.0)
                self.progressbar.set_show_text(False)
                self._running = False

        if not self._running:
            self.progressbar.set_fraction(0.25)
            self.progressbar.set_text ("do some magic!")
            self.progressbar.set_show_text (True)
            self._running = asyncio.async(coro())
    
    def on_stop(self, button):
        if self._running:
            self._running.cancel()

            
asyncio.set_event_loop_policy(gbulb.GtkEventLoopPolicy())

win = ProgressBarWindow()
win.connect("delete-event", Gtk.main_quit)
win.show_all()

asyncio.get_event_loop().run_forever()


