#!/usr/bin/env python -u

"""
Usage:
    computer [options]

Options:
    -h, --help          Show this page
    --debug             Show debug logging
    --verbose           Show verbose logging
    --prompt=<prompt>   Prompt to use
"""
from docopt import docopt
import logging
import multiprocessing.resource_tracker
import sys
import os
import speech_recognition as sr
import time
import string
import json
from . import functions
from . import llm
from . import voice
from .ui import VoiceApp

# Warm up the multiprocessing resource tracker before Textual takes over,
# avoids a Python 3.13 bug with bad file descriptors.
multiprocessing.resource_tracker.ensure_running()

logger = logging.getLogger('computer')


def parse_args(args):
    parsed_args = docopt(__doc__, args)
    if parsed_args['--debug']:
        logging.basicConfig(level=logging.DEBUG)
    elif parsed_args['--verbose']:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    return parsed_args


def recognize_audio(r, source):
    try:
        logger.debug("Listening... (energy_threshold=%s)", r.energy_threshold)
        audio_data = r.listen(source, timeout=5, phrase_time_limit=30)
        duration = len(audio_data.frame_data) / (audio_data.sample_rate * audio_data.sample_width)
        logger.info("Captured %.1fs of audio (threshold=%s)", duration, r.energy_threshold)
        if duration < 0.5:
            logger.debug("Audio too short (%.1fs), skipping recognition", duration)
            return ""
        text = r.recognize_whisper(audio_data)
    except sr.WaitTimeoutError:
        logger.debug("Listen timed out waiting for speech")
        text = ""
    return text


def audio_loop(prompt=None, on_display=None, on_status=None, on_exit=None):
    """Initialize Claude and listen/respond loop."""
    r = sr.Recognizer()
    r.pause_threshold = 3.0
    r.dynamic_energy_threshold = False
    r.energy_threshold = 300
    try:
        import pyaudio
        _pa = pyaudio.PyAudio()
        default_idx = _pa.get_default_input_device_info()["index"]
        default_name = _pa.get_default_input_device_info()["name"]
        logger.info("Default input device: [%d] %s", default_idx, default_name)
        # List all input devices for diagnostics
        for i in range(_pa.get_device_count()):
            info = _pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                logger.info("  Input device [%d]: %s (channels=%d, rate=%.0f)",
                            i, info["name"], info["maxInputChannels"], info["defaultSampleRate"])
        _pa.terminate()
        mic = sr.Microphone(sample_rate=16000)
        _idx = mic.device_index if mic.device_index is not None else default_idx
        mic_name = sr.Microphone.list_microphone_names()[_idx]
        logger.info("Using microphone: [%d] %s", _idx, mic_name)
        print(f"Microphone: {mic_name}")
        source = mic.__enter__()
        if source.stream is None:
            raise OSError("Microphone stream failed to open")
    except OSError as e:
        logger.error("Could not open microphone: %s", e)
        print("Error: Could not open microphone. Check that a microphone is "
              "connected and that microphone access is allowed in System Settings.")
        if on_exit:
            on_exit()
        return
    try:
        if on_status:
            on_status("Calibrating microphone...")
        r.adjust_for_ambient_noise(source, duration=2)
        logger.info("Calibrated energy threshold: %s", r.energy_threshold)
        # Read a short sample and check actual audio levels
        import audioop
        sample = source.stream.read(source.CHUNK)
        rms = audioop.rms(sample, source.SAMPLE_WIDTH)
        logger.info("Audio level check: RMS=%d from %d bytes", rms, len(sample))
        # Ensure threshold is in a usable range
        r.energy_threshold = max(r.energy_threshold, 100)
        r.energy_threshold = min(r.energy_threshold, 500)
        logger.info("Energy threshold set to %s", r.energy_threshold)

        if on_status:
            on_status("Initializing Claude...")
        response = llm.init_conversation()
        if on_display:
            on_display("", response)
        voice.say(response)

        if on_status:
            on_status("Listening...")
        else:
            print("Ready")
        while True:
            try:
                text = recognize_audio(r, source)
            except KeyboardInterrupt:
                if on_exit:
                    on_exit()
                return

            text = text.strip().lower()
            text = text.translate(str.maketrans('', '', string.punctuation))
            if text == "" or text == "15 15 15 15 15 15 15":
                continue

            if on_status:
                on_status("Processing...")
            print(f"You said '{text}'")

            try:
                if prompt:
                    text = prompt + " " + text
                response = llm.generate_response(text)
                speech, json_data = llm.parse_response(response)
                if on_display:
                    on_display(text, response)
                if json_data:
                    print(json.dumps(json_data, indent=2))

                # If Claude called a function, execute it and get a spoken summary
                if json_data and "function" in json_data:
                    result = functions.call(json_data["function"], json_data.get("args", {}))
                    print(json.dumps(result, indent=2))
                    image_path = result.get("path", "") if isinstance(result, dict) else ""
                    if image_path and image_path.endswith(".png"):
                        follow_up_prompt = (
                            f"Read the image at {image_path} and describe what you see. "
                            "Be brief and conversational."
                        )
                    else:
                        follow_up_prompt = (
                            f"Function {json_data['function']} returned: {json.dumps(result)}. "
                            "Summarize the result conversationally."
                        )
                    follow_up = llm.generate_response(follow_up_prompt)
                    speech, _ = llm.parse_response(follow_up)
                    if on_display:
                        on_display(text, follow_up)

                voice.say(speech)
            except SystemExit:
                if on_exit:
                    on_exit()
                return

            if on_status:
                on_status("Listening...")
            time.sleep(1)
    finally:
        if source.stream is not None:
            mic.__exit__(None, None, None)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parsed_args = parse_args(args)

    prompt_file = parsed_args['--prompt']
    prompt = None
    if prompt_file and os.path.exists(prompt_file):
        with open(prompt_file, 'r') as f:
            prompt = f.read()

    try:
        if parsed_args['--debug']:
            audio_loop(prompt)
        else:
            app = VoiceApp(lambda: audio_loop(
                prompt,
                on_display=app.display_callback,
                on_status=app.status_callback,
                on_exit=app.exit,
            ))
            app.run()
    except KeyboardInterrupt:
        pass
    finally:
        if not parsed_args['--debug']:
            os.system("stty sane && clear")

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
