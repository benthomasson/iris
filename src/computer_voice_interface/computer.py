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
        audio_data = r.listen(source, timeout=5)
        text = r.recognize_whisper(audio_data)
    except sr.WaitTimeoutError:
        text = ""
    return text


def audio_loop(prompt=None, on_display=None, on_status=None, on_exit=None):
    """Initialize Claude and listen/respond loop."""
    if on_status:
        on_status("Initializing Claude...")
    response = llm.init_conversation()
    if on_display:
        on_display("", response)
    voice.say(response)

    r = sr.Recognizer()
    with sr.Microphone(sample_rate=8000) as source:
        if on_status:
            on_status("Calibrating microphone...")
        r.adjust_for_ambient_noise(source, duration=5)
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
            if on_display:
                on_display(text, response)
            voice.say(response)

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
