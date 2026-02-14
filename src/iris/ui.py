import os
import queue

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Input, Static
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


class SleepUpdate(Message):
    def __init__(self, sleeping: bool):
        super().__init__()
        self.sleeping = sleeping


class MuteUpdate(Message):
    def __init__(self, muted: bool):
        super().__init__()
        self.muted = muted


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
    #text-input {
        dock: bottom;
        display: none;
    }
    Vertical.sleeping {
        opacity: 0.5;
    }
    Vertical.muted {
        background: darkred;
    }
    """

    TITLE = "Iris"
    BINDINGS = [
        ("q", "force_quit", "Quit"),
        ("ctrl+q", "force_quit", "Quit"),
        ("ctrl+c", "force_quit", "Quit"),
    ]

    def __init__(self, worker_fn, quiet=False):
        super().__init__()
        self._worker_fn = worker_fn
        self._quiet = quiet
        self.input_queue = queue.Queue()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("You said:", id="user-label"),
            Static("", id="user-text"),
            Static("Claude:", id="response-label"),
            Static("Starting...", id="response-text"),
        )
        yield Input(placeholder="Type a message...", id="text-input")
        yield Static("Starting...", id="status")

    def on_mount(self) -> None:
        if self._quiet:
            self.query_one("#text-input").styles.display = "block"
            self.query_one("#text-input").focus()
        self.run_worker(self._worker_fn, thread=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            self.input_queue.put(text)
            event.input.value = ""

    def on_display_update(self, message: DisplayUpdate) -> None:
        if message.user_text:
            self.query_one("#user-text", Static).update(message.user_text)
        self.query_one("#response-text", Static).update(message.response_text)
        if self._quiet:
            self.query_one("#text-input").focus()

    def on_status_update(self, message: StatusUpdate) -> None:
        self.query_one("#status", Static).update(message.text)

    def on_sleep_update(self, message: SleepUpdate) -> None:
        container = self.query_one("Vertical")
        if message.sleeping:
            container.add_class("sleeping")
        else:
            container.remove_class("sleeping")

    def on_mute_update(self, message: MuteUpdate) -> None:
        container = self.query_one("Vertical")
        if message.muted:
            container.add_class("muted")
        else:
            container.remove_class("muted")

    def action_force_quit(self) -> None:
        """Force quit — kills worker thread and subprocesses."""
        os.system("stty sane && clear")
        os._exit(0)

    def display_callback(self, user_text: str, response_text: str) -> None:
        """Thread-safe callback for the FSM to update the display."""
        self.post_message(DisplayUpdate(user_text, response_text))

    def status_callback(self, text: str) -> None:
        """Thread-safe callback to update the status bar."""
        self.post_message(StatusUpdate(text))

    def sleep_callback(self, sleeping: bool) -> None:
        """Thread-safe callback to toggle sleep mode visuals."""
        self.post_message(SleepUpdate(sleeping))

    def mute_callback(self, muted: bool) -> None:
        """Thread-safe callback to toggle mute mode visuals."""
        self.post_message(MuteUpdate(muted))
