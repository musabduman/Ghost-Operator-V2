"""
handlers/signal_watcher.py — Harici sinyalleri (uyandir_sinyali.txt) izler.
"""
import os

class SignalWatcher:
 
    SIGNAL_FILE = "uyandir_sinyali.txt"
    INTERVAL_MS = 500
 
    def __init__(self, app):
        self.app = app
 
    def start(self):
        self._check()
 
    def _check(self):
        if os.path.exists(self.SIGNAL_FILE):
            try:
                os.remove(self.SIGNAL_FILE)
            except OSError:
                pass
            self._wake_up()
        self.app.after(self.INTERVAL_MS, self._check)
 
    def _wake_up(self):
        self.app.deiconify()
        self.app.attributes("-topmost", True)
        self.app.lift()
        self.app.focus_force()
        self.app.attributes("-alpha", 0.98)
        self.app.after(0, self.app.voice_handler.start_listening)