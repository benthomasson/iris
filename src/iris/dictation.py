#!/usr/bin/env python -u

"""
Usage:
    dictation [options]

Options:
    -h, --help          Show this page
    --debug             Show debug logging
    --verbose           Show verbose logging
"""
from docopt import docopt
import logging
import sys
import speech_recognition as sr
import time
from threading import Thread
from queue import Queue

logger = logging.getLogger("computer")

IGNORE_STRINGS = ['1.5% 1.5% 1.5% 1.5% 1.5% 1.5% 1.5%',
                  '2.5G 2.5G 2.5G 2.5G 2.5G',
                  '1,5% 1,5% 1,5% 1,5% 1,5% 1,5%',
                  '1.5kg 1.5kg 1.5kg 1.5kg',
                  '1 cdc 1 cdc 1 cdc 1 cdc 1 cdc',
                  '1.5% 1.5% 1.5% 1.5% 1.5%',
                  '1.5% 2.5% 1.5% 1.5% 1.5% 1.5% 1.5%',
                 ]


# background recognizer thread
def recognize_audio_thread(r, queue):
    while True:
        print('Waiting on audio...', file=sys.stderr)
        audio_data = queue.get()
        try:
            print("Recognizing...", file=sys.stderr)
            start = time.time()
            text = r.recognize_whisper(audio_data)
            print("Took ", time.time() - start, file=sys.stderr)
        except KeyboardInterrupt:
            return
        text = text.strip()
        if text == "":
            continue
        if text in IGNORE_STRINGS:
            continue

        print(text)


def parse_args(args):
    parsed_args = docopt(__doc__, args)
    if parsed_args["--debug"]:
        logging.basicConfig(level=logging.DEBUG)
    elif parsed_args["--verbose"]:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    return parsed_args


def listen_for_audio(r, source, queue):
    # read the audio data from the default microphone
    while True:
        try:
            print("Listening...", file=sys.stderr)
            audio_data = r.listen(source, timeout=5, phrase_time_limit=30)
            print("Got audio", file=sys.stderr)
            queue.put(audio_data)
        except sr.WaitTimeoutError:
            print("Timeout", file=sys.stderr)
            pass


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parse_args(args)

    r = sr.Recognizer()
    with sr.Microphone(sample_rate=8000) as source:
        r.adjust_for_ambient_noise(source, duration=5)
        print("Ready", file=sys.stderr)
        audio_queue = Queue()
        recognizer_thread = Thread(target=recognize_audio_thread,
                                   args=(r, audio_queue))
        recognizer_thread.start()
        listen_for_audio(r, source, audio_queue)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
