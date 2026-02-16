# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Iris — a personal assistant with eyes, ears, and a voice. Combines OpenAI Whisper speech recognition with Claude CLI for a spoken assistant. macOS only (uses native `say` command for TTS). Features a full-screen Textual TUI, webcam vision, and local function calling via JSON blocks.

## Running

```bash
# Install in development mode
pip install -e .

# Or run via uv
uv run iris [options]
uv run iris --debug                        # no TUI, prints to stdout
uv run iris --quiet                        # text input, no speech output
uv run iris --debug --quiet                # text input via stdin
uv run iris --visual                       # periodic camera narration
uv run iris --passive                      # listen passively, respond when addressed
uv run iris --message="Ben,Mom"            # respond via iMessage to named contacts
uv run iris-dictation [--debug] [--verbose]
uv run iris-summarize [--chunk-size=<c>] [--tokens=<t>] <text-file>

# Dev dependencies
pip install -e ".[dev]"
```

### CLI Options

| Option | Description | Default |
|---|---|---|
| `--debug` | No TUI, prints to stdout | off |
| `--verbose` | Show verbose logging | off |
| `--quiet` | Text input, no speech output | off |
| `--visual` | Enable visual mode (periodic camera capture) | off |
| `--passive` | Start in passive mode (listen, respond only when addressed) | off |
| `--dictate` | Start in dictation mode (transcribe to file, query on wake) | off |
| `--message=<contacts>` | Message mode: respond via iMessage to named contacts (comma-separated) | none |
| `--no-camera` | Skip camera initialization | off |
| `--system=<file>` | Extra system prompt (appended to identity) | none |
| `--intro=<file>` | First user message sent after init | none |
| `--prompt=<file>` | Prepended to every user message | none |
| `--name=<name>` | Assistant name | Iris |
| `--voice=<voice>` | macOS TTS voice | Moira (Enhanced) |
| `--pitch=<pitch>` | Voice pitch | 50 |

## Prerequisites

- `claude` CLI installed and authenticated
- macOS (for `say` TTS command)
- Microphone access (not needed with `--quiet`)
- Webcam (for vision/capture)
- spaCy `en_core_web_sm` model for iris-summarize

## Architecture

**Data flow:** Microphone/text input → SpeechRecognition (Whisper, 16kHz) or stdin/TUI → text cleanup (lowercase, strip punctuation) → `llm.generate_response()` → `parse_response()` splits speech from JSON blocks → all function calls executed (`_execute_functions`) → combined results sent back to Claude for conversational summary (`_build_follow_up`) → `voice.say()` speaks text → macOS `say` at 180 wpm. Multiple function calls in a single response are supported.

**State machine** (in `computer.py`):
- **Active** — listening and responding. After each silence timeout with no speech, increments idle counter.
- **Inactive/sleeping** — ignores all input except wake words. Camera released. Triggered by idle timeout (25 cycles, ~125s) or `go_to_sleep` function. Wake by saying the assistant's name (fuzzy matched via Damerau-Levenshtein, edit distance ≤ 1) or "wake up".
- **Muted** — microphone input discarded, but visual mode captures continue on their interval. Only "unmute" is recognized.
- **Passive** — orthogonal flag (`PASSIVE_MODE`). All speech is buffered locally without sending to Claude. When the assistant's name is detected (via `is_wake_word()`), the full buffer is sent as conversation context, Claude responds, and the buffer clears. Auto-sleep is suppressed. Visual mode captures continue independently. Toggle via `--passive` flag, `start_passive_mode`/`stop_passive_mode` functions, or voice command.
- **Dictation** — orthogonal flag (`DICTATION_MODE`). All speech is written to a timestamped file in `~/.iris/dictation/` with `[HH:MM:SS]` prefixes, flushed immediately for crash safety. On wake word, last 100 lines of transcript sent to Claude as context; transcript keeps accumulating (does not clear). Claude can call `get_dictation_transcript()` to read older portions. Mutually exclusive with passive mode. Auto-sleep suppressed. Toggle via `--dictate` flag, `start_dictation`/`stop_dictation` functions, or voice command.
- **Message mode** — separate loop (`message_loop()` in `computer.py`). Polls `~/Library/Messages/chat.db` via `sqlite3` CLI every 2 seconds for new incoming iMessages from specified contacts. Each message is sent through the same Claude conversation and function pipeline. Responses are sent back as iMessages via AppleScript. Contact names are resolved to phone handles via Contacts.app JXA. TTS is suppressed. Camera still available for capture functions. Activated via `--message=<contacts>` (comma-separated names).

**Visual mode:** When enabled (via `--visual` flag or `start_visual_mode` function), captures a webcam frame every 10 seconds during idle/muted periods and sends it to Claude for narration. Uses shorter listen timeouts (3s timeout, 3s phrase limit) vs normal mode (5s timeout, 30s phrase limit).

**Key modules (all under `src/iris/`):**
- `computer.py` — Entry point (`iris`). Main loop with Textual TUI (or `--debug` for stdout). Manages active/inactive/muted/passive states, idle timeout, function call dispatch and follow-up. Watchdog thread wraps mic capture to detect hangs.
- `llm.py` — Claude CLI wrapper. `init_conversation()` starts a session via `claude -p` with the system prompt (identity + function catalog). `generate_response()` continues it via `claude -c -p` (with `--allowedTools Read` for image reading). `parse_response()` extracts all JSON function blocks from a response (returns a list). Configurable assistant name with identity lookup. `MESSAGE_MODE` flag selects an iMessage-appropriate system prompt.
- `functions.py` — Local function registry. Use `@register(name, description, parameters)` decorator to add functions Claude can call. JSON format: `{"function": "name", "args": {...}}`. Includes weather (Open-Meteo), time, timers, calculator, notes, Wikipedia, unit conversion, camera capture, visual/mute/passive/dictation mode, iMessage (send/read/list), sleep, shutdown. Stubs for home automation, music.
- `voice.py` — TTS wrapper around macOS `say` command. Configurable voice, rate (180 wpm), and pitch. Respects `QUIET` flag.
- `ui.py` — Textual full-screen TUI showing user speech and Claude response. Status bar, sleep (dimmed) and mute (red background) visual states. Text input widget in quiet mode. Press `q` to quit.
- `dictation.py` — Standalone transcription tool (`iris-dictation`). Threaded listener + recognizer with Whisper hallucination filtering.
- `summarize.py` — Text summarization via LLM (`iris-summarize`). Chunks text using spaCy then summarizes each chunk.

**Adding new functions:** Add a `@register` decorated function in `functions.py`. It will automatically appear in the system prompt sent to Claude. Functions raise `EnterInactiveMode` to trigger sleep or `SystemExit` to shut down.

## Code Conventions

- CLI argument parsing uses `docopt` (docstring-based)
- Internal imports use relative style (`from . import llm`)
- Logging via standard `logging` module; controlled by `--debug`/`--verbose` flags. Logs always written to `~/.iris/logs/`.
- Whisper hallucination strings (e.g., repeated "15 15 15...", "1.5%") are filtered out
- Audio: 16kHz sample rate, 1.5s pause threshold, energy threshold 300 (dynamic adjustment disabled)
- Camera warms up at startup (30 frames for auto-exposure), released on sleep
- Python 3.13 workaround: `multiprocessing.resource_tracker.ensure_running()` called at import time to avoid fd bug with Textual
- Camera captures stored in `~/.iris/captures/`, notes in `~/.cvi_notes/`, dictation transcripts in `~/.iris/dictation/`
