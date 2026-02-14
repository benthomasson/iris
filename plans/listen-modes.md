# Listening Modes: Active / Inactive (Sleep)

## Context

Iris currently listens continuously and sends all input to Claude. This wastes resources when the user isn't actively talking, and the camera light stays on permanently. Adding an inactive "sleep" mode lets Iris release the camera (light off = visual indicator) and only listen locally for wake words, without calling Claude.

## Changes

### 1. `src/iris/functions.py` — Add sleep function + exception

- Add `EnterInactiveMode` exception class (follows the `SystemExit` pattern used by `shutdown()`)
- Register `go_to_sleep` function that raises `EnterInactiveMode`
  - Description tells Claude to use it when user says "pause", "take a break", "go to sleep", etc.

### 2. `src/iris/computer.py` — Restructure main loop

**New constants/helpers:**
- `IDLE_CYCLES_BEFORE_INACTIVE = 5` (~25s of silence with 5s listen timeout)
- `is_wake_word(text)` — checks normalized text for: assistant name, "hey {name}", "hello {name}", "wake up"

**Main loop gets two branches:**

**Inactive mode:**
- Still captures audio via `recognize_audio()`
- Filters hallucinations as before
- Checks for wake words locally (no Claude call)
- On wake word: `init_camera()`, `voice.say("I'm here.")`, switch to active

**Active mode (current behavior + idle tracking):**
- `idle_count` increments on empty input, resets on real input
- After 5 consecutive empty cycles (mic mode only, not quiet mode): release camera, `voice.say("Going to sleep.")`, switch to inactive
- Catch `EnterInactiveMode` from `functions.call()`: same transition as idle timeout
- `SystemExit` handling unchanged

**Status bar messages:**
- Active: "Listening..." (unchanged)
- Inactive: "Sleeping (say 'Iris' to wake)"

### No changes needed
- `llm.py` — `go_to_sleep` auto-appears in system prompt via `@register`
- `ui.py` — existing callbacks handle status/display updates
- `voice.py` — `voice.say()` used directly for transition announcements

## Verification

1. Run `uv run iris --debug` and say "take a break" — should hear "Going to sleep.", camera light off
2. Say "Iris" or "wake up" — should hear "I'm here.", camera light on
3. Stay silent for ~25s — should auto-sleep
4. Say "goodbye" — should still shutdown normally
5. Run `uv run iris --debug --quiet` — idle timeout should NOT trigger (text mode)
