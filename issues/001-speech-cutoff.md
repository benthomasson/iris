# Speech Recognition Cuts Off Early on First Few Prompts

## Observed Behavior

Speech recognition clips or cuts off user input during the first few interactions after startup. After several prompts, recognition improves and captures full utterances reliably.

## Likely Cause

The ambient noise calibration (`adjust_for_ambient_noise`) runs once at startup for 5 seconds. If there is any transient noise during calibration, the energy threshold gets set too high, causing the recognizer to miss the beginning of speech or stop listening too early.

After a few prompts, SpeechRecognition's `dynamic_energy_threshold` (enabled by default) adjusts itself based on actual audio, which is why it improves over time.

## Current Audio Settings

- Sample rate: 16kHz
- `pause_threshold`: 2.0s
- `phrase_time_limit`: 30s
- Ambient noise calibration: 5s at startup
- `dynamic_energy_threshold`: default (True)

## Possible Fixes

1. **Shorten calibration duration** — Reduce from 5s to 2-3s to lower the chance of capturing transient noise
2. **Set a fixed energy threshold** — e.g. `r.energy_threshold = 300` and set `r.dynamic_energy_threshold = False` to prevent overcorrection
3. **Lower the initial threshold** — Set `r.energy_threshold` to a lower value after calibration so it errs on the side of capturing more audio
4. **Re-calibrate periodically** — Run `adjust_for_ambient_noise` between prompts (adds latency)
5. **Log the energy threshold** — Add debug logging of `r.energy_threshold` after calibration and during recognition to understand what values are being used

## Files

- `src/computer_voice_interface/computer.py` — `audio_loop()` and `recognize_audio()`
