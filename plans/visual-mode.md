# Visual Mode — Periodic Camera Frames to Claude

## Context

Iris can capture images on demand via `capture_image`, but only when explicitly asked. A "visual mode" sends camera frames to Claude every ~10s even without audio input, enabling proactive narration — reading books aloud to children, announcing chess moves, describing a scene as it changes.

## Design

Visual mode is a modifier on active mode (not a separate state). When enabled, each empty listen cycle checks if ~10s have passed since the last capture and, if so, captures a frame and sends it to Claude for narration. Audio input still works normally alongside it. Auto-sleep is disabled while visual mode is on.

### How images reach Claude

Current flow (from `capture_image` function call):
1. `functions.capture_image()` saves a PNG to `~/.iris/captures/`
2. Follow-up prompt: `"Read the image at {path} and describe what you see."`
3. `claude -c -p ... --allowedTools Read` reads the image file

Visual mode reuses this same mechanism — capture frame, send prompt with path.

## Changes

### 1. `src/iris/functions.py` — Add visual mode toggle functions

- Add module-level `VISUAL_MODE = False` flag
- Register `start_visual_mode()`: sets `VISUAL_MODE = True`, returns status
  - Description: "Start visual mode to periodically capture and describe what the camera sees. Use when user says 'start watching', 'watch this', 'look at this', etc."
- Register `stop_visual_mode()`: sets `VISUAL_MODE = False`, returns status
  - Description: "Stop visual mode. Use when user says 'stop watching', 'stop looking', etc."

### 2. `src/iris/computer.py` — Periodic capture in main loop

**New constant:**
- `VISUAL_INTERVAL = 10` (seconds between captures)

**CLI flag:**
- Add `--visual` option to docstring and `parse_args`
- When set, `functions.VISUAL_MODE = True` at startup

**Main loop changes (active mode, empty input branch):**

After the existing hallucination/empty check, before incrementing `idle_count`:
```
if functions.VISUAL_MODE and r is not None:
    idle_count = 0  # don't auto-sleep in visual mode
    now = time.time()
    if now - last_visual_capture >= VISUAL_INTERVAL:
        last_visual_capture = now
        result = functions.capture_image()
        if "path" in result:
            prompt_text = "Read the image at {path} and describe what you see. Narrate any changes or interesting details briefly."
            response = llm.generate_response(prompt_text)
            speech, _ = llm.parse_response(response)
            if on_display:
                on_display("[visual]", response)
            voice.say(speech)
    continue
```

**Initialize `last_visual_capture = 0.0`** alongside `active` and `idle_count`.

**Active mode with speech input:** reset `last_visual_capture = time.time()` so the timer restarts after user interaction (avoid narrating right after the user spoke).

### 3. `src/iris/computer.py` — Docstring/CLI

Add to docstring:
```
    --visual                Enable visual mode (periodic camera capture)
```

### No changes needed
- `llm.py` — reuses existing `generate_response()` with `--allowedTools Read`
- `ui.py` — existing `on_display` callback shows visual updates
- `voice.py` — `voice.say()` speaks narrations

## Verification

1. `uv run iris --debug --visual` — should capture and narrate every ~10s even with no speech
2. Say "stop watching" — periodic captures stop, normal active mode continues
3. Say "start watching" — resumes periodic captures
4. Speak during visual mode — response works normally, visual timer resets
5. `uv run iris --debug` (no --visual) — no periodic captures, existing behavior unchanged
6. Visual mode prevents auto-sleep (idle_count stays 0)
