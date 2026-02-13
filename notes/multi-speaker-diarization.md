# Multi-Speaker Support via Speaker Diarization

## Goal

Distinguish multiple people in a conversation, assign them names, and attribute each utterance to the correct speaker before sending to Claude. This would let Claude maintain context about who said what and respond accordingly.

## Current State

The voice interface works well for a single human talking to the computer. All recognized speech is treated as coming from one unnamed user.

## Recommended Approach: WhisperX + pyannote

**WhisperX** combines Whisper transcription with pyannote speaker diarization in one pipeline. It would replace the current `recognize_whisper` call and provide:

- Word-level timestamps
- Speaker labels (speaker_0, speaker_1, etc.)
- Transcription in one pass

**pyannote-audio** is the underlying diarization model (state-of-the-art, ~11% DER). Requires a HuggingFace token to download pretrained models.

## How It Could Work

1. **Enrollment phase** — On first use, each person says their name while speaking alone. The system captures a voice embedding for each speaker and maps it to their name.
2. **Recognition** — During conversation, WhisperX diarizes the audio and assigns speaker labels. The system matches embeddings against enrolled speakers to resolve labels to names.
3. **Attributed prompts** — Instead of sending "what time is it" to Claude, send "Alice: what time is it". Claude can then respond personally and track who asked what.
4. **Persistence** — Store speaker embeddings and name mappings to disk so enrollment survives restarts.

## Libraries

| Library | Purpose | Notes |
|---------|---------|-------|
| [WhisperX](https://github.com/m-bain/whisperX) | Transcription + diarization | Drop-in replacement for current Whisper usage |
| [pyannote-audio](https://github.com/pyannote/pyannote-audio) | Speaker diarization engine | Best accuracy, PyTorch-based, needs HuggingFace token |
| [NVIDIA NeMo](https://github.com/NVIDIA/NeMo) | Alternative diarization | Faster on NVIDIA GPUs, heavier dependency |

## Open Questions

- How many speakers can it reliably distinguish? (pyannote handles up to ~20)
- Latency impact — diarization adds processing time per utterance
- Can enrollment work with short samples (a few seconds) or does it need longer recordings?
- Should unknown speakers get a generic label ("Guest") or be prompted to enroll?
- How to handle overlapping speech?

## Implementation Phases

1. **Phase 1** — Replace `recognize_whisper` with WhisperX, get speaker labels (speaker_0, speaker_1) working
2. **Phase 2** — Add speaker enrollment (voice embedding + name mapping)
3. **Phase 3** — Send attributed prompts to Claude ("Alice: ..." / "Bob: ...")
4. **Phase 4** — Persist speaker profiles to disk
