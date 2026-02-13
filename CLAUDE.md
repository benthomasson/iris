# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A voice interface that combines OpenAI Whisper speech recognition with a local LLM (llama3 via Ollama) to create a spoken computer assistant. macOS only (uses native `say` command for TTS).

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Main voice interface
python3 computer.py [--debug] [--verbose] [--prompt=<file>]

# Dictation mode (continuous transcription)
python3 dictation.py [--debug] [--verbose]

# Text summarization
python3 summarize.py [--chunk-size=<c>] [--tokens=<t>] <text-file>
```

## Prerequisites

- Ollama running locally with `llama3` model pulled
- macOS (for `say` TTS command)
- Microphone access
- `API_KEY` env var (legacy OpenAI key, referenced in computer.py but LLM calls now go through Ollama)
- spaCy `en_core_web_sm` model for summarize.py

## Architecture

**Finite State Machine (computer_fsm.py)** — Core pattern. Three states:
- **InitialState** — Listens for wake words ("computer", "hello computer", "good morning computer"). Transitions to ComputerState or ShutdownState.
- **ComputerState** — Active mode. Non-keyword input is sent to the LLM and the response is spoken aloud. Say "exit" to return to InitialState.
- **ShutdownState** — Says goodbye via LLM, then raises SystemExit.

**Data flow:** Microphone → SpeechRecognition (Whisper) → text cleanup (lowercase, strip punctuation) → FSM.run(text) → state transition or LLM response → voice.say() → macOS `say`

**Key modules:**
- `computer.py` — Entry point. Audio capture loop, feeds recognized text into FSM.
- `computer_fsm.py` — StateMachine/State base classes + InitialState/ComputerState/ShutdownState.
- `llama2.py` — LLM wrapper. Despite the filename, uses `llama3` model via `ollama.generate()`.
- `voice.py` — TTS wrapper around macOS `say` command.
- `dictation.py` — Standalone transcription tool. Uses threading: one thread listens, another recognizes (queue-based).
- `summarize.py` — Chunks text with spaCy, summarizes each chunk via LLM.

**Threading model (dictation.py):** Listener thread captures audio into a Queue; recognizer thread consumes from the Queue. This prevents listening lockups during recognition.

## Code Conventions

- CLI argument parsing uses `docopt` (docstring-based)
- Logging via standard `logging` module; controlled by `--debug`/`--verbose` flags
- Whisper hallucination strings (e.g., repeated "1.5%") are filtered out in IGNORE_STRINGS
- Audio captured at 8000 Hz sample rate with 5-second ambient noise calibration
