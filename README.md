# Iris

A personal assistant with eyes, ears, and a voice. Combines OpenAI Whisper speech recognition with the Claude CLI for a spoken computer assistant with webcam vision and local function calling.

macOS only (uses native `say` command for TTS).

## Setup

```bash
# Requires claude CLI installed and authenticated
# Requires macOS with microphone and webcam access

pip install -e .
# or
uv run iris
```

## Usage

```bash
iris [options]
```

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
| `--no-shutter` | Disable camera shutter sound | off |
| `--system=<file>` | Extra system prompt (appended to identity) | none |
| `--intro=<file>` | First user message sent after init | none |
| `--prompt=<file>` | Prepended to every user message | none |
| `--name=<name>` | Assistant name | Iris |
| `--voice=<voice>` | macOS TTS voice | Moira (Enhanced) |
| `--pitch=<pitch>` | Voice pitch | 50 |

### Examples

```bash
iris                          # Full TUI with voice
iris --debug                  # stdout mode with voice
iris --quiet                  # TUI with text input, no speech
iris --debug --quiet          # stdin/stdout, no speech
iris --visual                 # Periodic camera narration
iris --passive                # Listen passively, respond when addressed
iris --dictate                # Transcribe speech to file, query on wake
iris --message="Ben,Mom"      # Respond to iMessages from Ben and Mom
iris --voice=Daniel --pitch=40 --name=Bob
iris --system=chess.txt --intro=game_start.txt
```

## Features

- **Speech recognition** via OpenAI Whisper (local, 16kHz)
- **Text-to-speech** via macOS `say` with configurable voice, rate, and pitch
- **Webcam vision** — capture images and send to Claude for description
- **Visual mode** — periodic camera capture with narration (even while muted)
- **Local function calling** — Claude emits JSON blocks that are executed locally (multiple calls per response supported):
  - Weather (Open-Meteo, no API key), time/date, timers, calculator
  - Notes/reminders, Wikipedia summaries, unit conversion
  - Camera capture, visual mode toggle, mute/unmute
  - iMessage (send, read, list conversations)
  - Passive mode, dictation mode toggle
  - Sleep/wake, shutdown
  - Stubs for home automation, music
- **Full-screen Textual TUI** with status bar, sleep/mute visual states
- **Quiet mode** for text-only interaction (TUI text input or stdin)
- **Sleep/wake** — auto-sleeps after ~125s of silence; wake by saying the assistant's name (fuzzy matched)
- **Mute** — mic off but visual mode continues
- **Passive mode** — buffers speech locally, only sends to Claude when addressed by name
- **Dictation mode** — continuously transcribes speech to a timestamped file in `~/.iris/dictation/`, crash-safe (flushed per line). Say the assistant's name to query Claude about the transcript. Transcript accumulates across interactions. Useful for meetings, lectures, and brainstorming sessions.
- **Message mode** — polls iMessage for incoming texts from specified contacts, responds via iMessage. Each contact gets a separate Claude conversation (no context bleed). Same function calling as voice mode. Contact names resolved via Contacts.app.

## Other tools

```bash
iris-dictation [--debug] [--verbose]                        # Standalone transcription
iris-summarize [--chunk-size=<c>] [--tokens=<t>] <file>     # Text summarization (requires spaCy en_core_web_sm)
```
