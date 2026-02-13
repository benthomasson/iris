import os

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Static
from textual.message import Message


class DisplayUpdate(Message):
    def __init__(self, user_text: str, response_text: str):
        super().__init__()
        self.user_text = user_text
        self.response_text = response_text


class StatusUpdate(Message):
    def __init__(self, text: str):
        super().__init__()
        self.text = text


class VoiceApp(App):
    CSS = """
    #user-label {
        color: $text-muted;
        padding: 0 1;
    }
    #user-text {
        padding: 1 2;
        height: auto;
        max-height: 30%;
    }
    #response-label {
        color: $text-muted;
        padding: 0 1;
    }
    #response-text {
        padding: 1 2;
        height: 1fr;
        text-style: bold;
    }
    #status {
        dock: bottom;
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    TITLE = "Computer Voice Interface"
    BINDINGS = [
        ("q", "force_quit", "Quit"),
        ("ctrl+q", "force_quit", "Quit"),
        ("ctrl+c", "force_quit", "Quit"),
    ]

    def __init__(self, worker_fn):
        super().__init__()
        self._worker_fn = worker_fn

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("You said:", id="user-label"),
            Static("", id="user-text"),
            Static("Claude:", id="response-label"),
            Static("Starting...", id="response-text"),
        )
        yield Static("Starting...", id="status")

    def on_mount(self) -> None:
        self.run_worker(self._worker_fn, thread=True)

    def on_display_update(self, message: DisplayUpdate) -> None:
        if message.user_text:
            self.query_one("#user-text", Static).update(message.user_text)
        self.query_one("#response-text", Static).update(message.response_text)

    def on_status_update(self, message: StatusUpdate) -> None:
        self.query_one("#status", Static).update(message.text)

    def action_force_quit(self) -> None:
        """Force quit — kills worker thread and subprocesses."""
        os._exit(0)

    def display_callback(self, user_text: str, response_text: str) -> None:
        """Thread-safe callback for the FSM to update the display."""
        self.post_message(DisplayUpdate(user_text, response_text))

    def status_callback(self, text: str) -> None:
        """Thread-safe callback to update the status bar."""
        self.post_message(StatusUpdate(text))
