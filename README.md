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
iris --voice=Daniel --pitch=40 --name=Bob
iris --system=chess.txt --intro=game_start.txt
```

## Features

- **Speech recognition** via OpenAI Whisper (local, 16kHz)
- **Text-to-speech** via macOS `say` with configurable voice, rate, and pitch
- **Webcam vision** — capture images and send to Claude for description
- **Visual mode** — periodic camera capture with narration (even while muted)
- **Local function calling** — Claude emits JSON blocks that are executed locally:
  - Weather (Open-Meteo, no API key), time/date, timers, calculator
  - Notes/reminders, Wikipedia summaries, unit conversion
  - Camera capture, visual mode toggle, mute/unmute
  - Sleep/wake, shutdown
  - Stubs for home automation, music, messaging
- **Full-screen Textual TUI** with status bar, sleep/mute visual states
- **Quiet mode** for text-only interaction (TUI text input or stdin)
- **Sleep/wake** — auto-sleeps after ~125s of silence; wake by saying the assistant's name (fuzzy matched)
- **Mute** — mic off but visual mode continues

## Other tools

```bash
iris-dictation [--debug] [--verbose]                        # Standalone transcription
iris-summarize [--chunk-size=<c>] [--tokens=<t>] <file>     # Text summarization (requires spaCy en_core_web_sm)
```
