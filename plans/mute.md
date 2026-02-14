# Mute Microphone Mode

## Context

During visual mode (e.g., RPG games), users need to discuss secrets without Iris hearing. Mute mode silences the mic while visual mode keeps capturing and narrating. The TUI turns red to indicate mute is active.

## Design

Mute is a modifier on active mode (like visual mode). When muted:
- All audio input is discarded (treated as empty)
- Visual mode captures continue normally
- Auto-sleep is suppressed
- Claude is told the mic is muted so it knows to keep narrating without expecting speech

## Changes

### 1. `src/iris/functions.py` — Add mute toggle functions

- Add module-level `MUTED = False` flag
- Register `mute_microphone()`: sets `MUTED = True`, returns status
  - Description: "Mute the microphone. Use when user says 'mute', 'mute mic', 'stop listening but keep watching', etc. Visual mode continues working."
- Register `unmute_microphone()`: sets `MUTED = False`, returns status
  - Description: "Unmute the microphone. Use when user says 'unmute', 'unmute mic', 'start listening again', etc."

### 2. `src/iris/computer.py` — Skip audio when muted

After text cleanup (`text.translate(...)`) and before the `if text == ""` check, add a muted guard:

```python
if functions.MUTED and r is not None and not quiet:
    idle_count = 0
    now = time.time()
    if functions.VISUAL_MODE and now - last_visual_capture >= VISUAL_INTERVAL:
        last_visual_capture = now
        result = functions.capture_image()
        if isinstance(result, dict) and "path" in result:
            prompt_text = (
                f"Read the image at {result['path']} and describe what you see. "
                "Narrate any changes or interesting details briefly."
            )
            response = llm.generate_response(prompt_text)
            speech, _ = llm.parse_response(response)
            if on_display:
                on_display("[visual]", response)
            voice.say(speech)
    continue
```

All audio is discarded regardless of content, but visual captures still fire on schedule.

### 3. `src/iris/computer.py` — Fire mute callback + status after function execution

In the function execution block, after any function call completes, check if mute state changed:

```python
if json_data and json_data.get("function") in ("mute_microphone", "unmute_microphone"):
    if on_mute:
        on_mute(functions.MUTED)
    if on_status:
        on_status("Muted (visual mode active)" if functions.MUTED else "Listening...")
```

- Add `on_mute=None` parameter to `audio_loop()`
- Wire `on_mute=app.mute_callback` in `main()` TUI branch

### 4. `src/iris/ui.py` — Red screen when muted

Follow the existing `SleepUpdate` pattern:

- Add `MuteUpdate` message class
- Add CSS: `Vertical.muted { background: darkred; }`
- Add `on_mute_update` handler that adds/removes the `muted` class on `Vertical`
- Add `mute_callback` method (same pattern as `sleep_callback`)

## Verification

1. `uv run iris --debug --visual` — say "mute" → audio discarded, visual captures continue
2. Say "unmute" → normal listening resumes
3. TUI mode: screen background turns red on mute, normal on unmute
4. Mute without visual mode: mic silenced, no captures, no auto-sleep
5. Existing behavior unchanged when mute is never activated
