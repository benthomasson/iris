# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A voice interface that combines OpenAI Whisper speech recognition with Claude CLI to create a spoken computer assistant. macOS only (uses native `say` command for TTS).

## Running

```bash
# Install in development mode
pip install -e .

# Or run directly via uvx
uvx --from . cvi [--debug] [--verbose] [--prompt=<file>]
uvx --from . cvi-dictation [--debug] [--verbose]
uvx --from . cvi-summarize [--chunk-size=<c>] [--tokens=<t>] <text-file>

# Dev dependencies
pip install -e ".[dev]"
```

## Prerequisites

- `claude` CLI installed and authenticated
- macOS (for `say` TTS command)
- Microphone access
- spaCy `en_core_web_sm` model for cvi-summarize

## Package Structure

```
src/computer_voice_interface/   # all source code lives here
pyproject.toml                  # build config, dependencies, entry points
```

## Architecture

**Finite State Machine (computer_fsm.py)** — Core pattern. Three states:
- **InitialState** — Listens for wake words ("computer", "hello computer", "good morning computer"). Transitions to ComputerState or ShutdownState.
- **ComputerState** — Active mode. Non-keyword input is sent to the LLM and the response is spoken aloud. Say "exit" to return to InitialState.
- **ShutdownState** — Says goodbye via LLM, then raises SystemExit.

**Data flow:** Microphone → SpeechRecognition (Whisper) → text cleanup (lowercase, strip punctuation) → FSM.run(text) → state transition or LLM response → voice.say() → macOS `say`

**Key modules (all under `src/computer_voice_interface/`):**
- `computer.py` — Entry point (`cvi`). Audio capture loop, feeds recognized text into FSM.
- `computer_fsm.py` — StateMachine/State base classes + InitialState/ComputerState/ShutdownState.
- `llm.py` — LLM wrapper. Calls `claude -c -p` via subprocess. `init_conversation()` starts a new session on startup (without `-c`), then `generate_response()` continues it.
- `voice.py` — TTS wrapper around macOS `say` command.
- `dictation.py` — Standalone transcription tool (`cvi-dictation`). Uses threading: one thread listens, another recognizes (queue-based).
- `summarize.py` — Chunks text with spaCy, summarizes each chunk via LLM (`cvi-summarize`).

**Threading model (dictation.py):** Listener thread captures audio into a Queue; recognizer thread consumes from the Queue. This prevents listening lockups during recognition.

## Code Conventions

- CLI argument parsing uses `docopt` (docstring-based)
- Internal imports use relative style (`from . import llm`)
- Logging via standard `logging` module; controlled by `--debug`/`--verbose` flags
- Whisper hallucination strings (e.g., repeated "1.5%") are filtered out in IGNORE_STRINGS
- Audio captured at 8000 Hz sample rate with 5-second ambient noise calibration
