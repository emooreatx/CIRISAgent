from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Log, Static
from textual.containers import Horizontal, Vertical
import logging
import asyncio

class CIRISConsole(App):
    CSS_PATH = None
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_widget = None
        self.deferral_widget = None
        self.progress_widget = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical():
                self.progress_widget = Log(highlight=True, name="progress")
                yield Static("Wakeup / Dream Progress", classes="title")
                yield self.progress_widget
            with Vertical():
                self.log_widget = Log(highlight=True, name="log")
                yield Static("Log Output", classes="title")
                yield self.log_widget
            with Vertical():
                self.deferral_widget = Log(highlight=True, name="deferrals")
                yield Static("Deferrals", classes="title")
                yield self.deferral_widget
        yield Footer()

    def write_progress(self, msg: str):
        self.progress_widget.write(msg)

    def write_log(self, msg: str):
        self.log_widget.write(msg)

    def write_deferral(self, msg: str):
        self.deferral_widget.write(msg)

class TextualLogHandler(logging.Handler):
    def __init__(self, console_app: CIRISConsole):
        super().__init__()
        self.console_app = console_app
    def emit(self, record):
        msg = self.format(record)
        asyncio.run_coroutine_threadsafe(
            self.console_app.call_from_thread(self.console_app.write_log, msg),
            self.console_app.loop,
        )
