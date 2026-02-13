# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A voice interface that combines OpenAI Whisper speech recognition with Claude CLI to create a spoken computer assistant. macOS only (uses native `say` command for TTS). Features a full-screen Textual TUI and local function calling via JSON blocks.

## Running

```bash
# Install in development mode
pip install -e .

# Or run via uv
uv run cvi [--verbose] [--prompt=<file>]
uv run cvi --debug                        # no TUI, prints to stdout
uv run cvi-dictation [--debug] [--verbose]
uv run cvi-summarize [--chunk-size=<c>] [--tokens=<t>] <text-file>

# Dev dependencies
pip install -e ".[dev]"
```

## Prerequisites

- `claude` CLI installed and authenticated
- macOS (for `say` TTS command)
- Microphone access
- spaCy `en_core_web_sm` model for cvi-summarize

## Architecture

**Data flow:** Microphone → SpeechRecognition (Whisper, 16kHz) → text cleanup → `llm.generate_response()` → `parse_response()` splits speech/JSON → function execution if JSON contains `{"function": ...}` → `voice.say()` speaks non-JSON text → macOS `say` at 235 wpm

**Key modules (all under `src/computer_voice_interface/`):**
- `computer.py` — Entry point (`cvi`). Audio loop with Textual TUI (or `--debug` for stdout). Handles function call execution and follow-up.
- `llm.py` — Claude CLI wrapper. `init_conversation()` starts a session with the system prompt (includes available functions), `generate_response()` continues it via `claude -c -p`. `parse_response()` splits text from JSON blocks.
- `functions.py` — Local function registry. Use `@register(name, description, parameters)` decorator to add functions Claude can call. JSON format: `{"function": "name", "args": {...}}`. Currently includes `get_weather` stub.
- `voice.py` — TTS wrapper around macOS `say` command (235 wpm).
- `ui.py` — Textual full-screen TUI showing user speech and Claude response. Press `q` to quit.
- `dictation.py` — Standalone transcription tool (`cvi-dictation`).
- `summarize.py` — Text summarization via LLM (`cvi-summarize`).

**Adding new functions:** Add a `@register` decorated function in `functions.py`. It will automatically appear in the system prompt sent to Claude.

## Code Conventions

- CLI argument parsing uses `docopt` (docstring-based)
- Internal imports use relative style (`from . import llm`)
- Logging via standard `logging` module; controlled by `--debug`/`--verbose` flags
- Whisper hallucination strings (e.g., repeated "1.5%") are filtered out
- Audio: 16kHz sample rate, 2s pause threshold, 30s phrase time limit, 5s ambient noise calibration
- Python 3.13 workaround: `multiprocessing.resource_tracker.ensure_running()` called at import time to avoid fd bug with Textual
