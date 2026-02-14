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
iris --voice=Daniel --pitch=40 --name=Bob
iris --system=chess.txt --intro=game_start.txt
```

## Features

- Speech recognition via OpenAI Whisper (local)
- Text-to-speech via macOS `say` with configurable voice
- Webcam capture and vision (sends images to Claude)
- Local function calling (weather, timer, calculator, notes, Wikipedia, unit conversion)
- Full-screen Textual TUI or debug stdout mode
- Quiet mode for text-only interaction

## Other tools

```bash
iris-dictation [--debug] [--verbose]                        # Standalone transcription
iris-summarize [--chunk-size=<c>] [--tokens=<t>] <file>     # Text summarization
```
