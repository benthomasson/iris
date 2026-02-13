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
        audio_data = r.listen(source, timeout=5, phrase_time_limit=30)
        duration = len(audio_data.frame_data) / (audio_data.sample_rate * audio_data.sample_width)
        logger.info("Captured %.1fs of audio (threshold=%s)", duration, r.energy_threshold)
        text = r.recognize_whisper(audio_data)
    except sr.WaitTimeoutError:
        text = ""
    return text


def audio_loop(prompt=None, on_display=None, on_status=None, on_exit=None):
    """Initialize Claude and listen/respond loop."""
    r = sr.Recognizer()
    r.pause_threshold = 3.0
    r.dynamic_energy_threshold = False
    r.energy_threshold = 300
    with sr.Microphone(sample_rate=16000) as source:
        if on_status:
            on_status("Calibrating microphone...")
        r.adjust_for_ambient_noise(source, duration=2)
        # Use calibrated value as a floor but don't go above 500
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
                follow_up = llm.generate_response(
                    f"Function {json_data['function']} returned: {json.dumps(result)}. "
                    "Summarize the result conversationally."
                )
                speech, _ = llm.parse_response(follow_up)
                if on_display:
                    on_display(text, follow_up)

            voice.say(speech)

            if on_status:
                on_status("Listening...")
            time.sleep(1)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parsed_args = parse_args(args)

    prompt_file = parsed_args['--prompt']
    prompt = None
    if prompt_file and os.path.exists(prompt_file):
        with open(prompt_file, 'r') as f:
            prompt = f.read()

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

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
