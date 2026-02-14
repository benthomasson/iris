#!/usr/bin/env python -u

"""
Usage:
    iris [options]

Options:
    -h, --help              Show this page
    --debug                 Show debug logging
    --verbose               Show verbose logging
    --quiet                 Text input, no speech output
    --system=<file>         Extra system prompt (appended to identity)
    --intro=<file>          First user message sent after init
    --prompt=<file>         Prepended to every user message
    --name=<name>           Assistant name [default: Iris]
    --voice=<voice>         macOS TTS voice [default: Moira (Enhanced)]
    --pitch=<pitch>         Voice pitch [default: 50]
    --visual                Enable visual mode (periodic camera capture)
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
from .functions import EnterInactiveMode
from . import llm
from . import voice
from .ui import VoiceApp

IDLE_CYCLES_BEFORE_INACTIVE = 5  # ~25s of silence with 5s listen timeout
VISUAL_INTERVAL = 10  # seconds between visual mode captures

# Warm up the multiprocessing resource tracker before Textual takes over,
# avoids a Python 3.13 bug with bad file descriptors.
multiprocessing.resource_tracker.ensure_running()

logger = logging.getLogger('computer')


LOG_DIR = os.path.expanduser("~/.iris/logs")


def parse_args(args):
    parsed_args = docopt(__doc__, args)
    os.makedirs(LOG_DIR, exist_ok=True)
    from datetime import datetime
    log_file = os.path.join(LOG_DIR, datetime.now().strftime("%Y%m%d_%H%M%S.log"))
    handlers = [logging.FileHandler(log_file)]
    if parsed_args['--debug']:
        level = logging.DEBUG
        handlers.append(logging.StreamHandler())
    elif parsed_args['--verbose']:
        level = logging.INFO
        handlers.append(logging.StreamHandler())
    else:
        level = logging.INFO
    logging.basicConfig(level=level, handlers=handlers,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logger.info("Log file: %s", log_file)
    return parsed_args


def recognize_audio(r, source):
    try:
        timeout = 3 if functions.VISUAL_MODE else 5
        phrase_limit = 3 if functions.VISUAL_MODE else 30
        logger.debug("Listening... (energy_threshold=%s)", r.energy_threshold)
        audio_data = r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
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


def get_input(r=None, source=None, input_queue=None):
    """Get user input from mic, stdin, or TUI queue."""
    if input_queue is not None:
        return input_queue.get()
    if r is None:
        try:
            return input("> ")
        except (EOFError, KeyboardInterrupt):
            return None
    return recognize_audio(r, source)


def is_wake_word(text):
    """Check if text contains a wake word to exit inactive mode."""
    name = llm.ASSISTANT_NAME.lower()
    words = text.lower().split()
    if name in words:
        return True
    if "wake" in words and "up" in words:
        return True
    return False


def audio_loop(prompt=None, on_display=None, on_status=None, on_sleep=None,
               on_mute=None, on_exit=None, quiet=False, input_queue=None, intro=None):
    """Initialize Claude and listen/respond loop."""
    mic = None
    source = None
    r = None

    if quiet:
        voice.QUIET = True
    else:
        r = sr.Recognizer()
        r.pause_threshold = 1.5
        r.dynamic_energy_threshold = False
        r.energy_threshold = 300
        try:
            import pyaudio
            _pa = pyaudio.PyAudio()
            default_idx = _pa.get_default_input_device_info()["index"]
            default_name = _pa.get_default_input_device_info()["name"]
            logger.info("Default input device: [%d] %s", default_idx, default_name)
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

        logger.info("Calibrating microphone...")
        if on_status:
            on_status("Calibrating microphone...")
        import threading
        calibrated = threading.Event()
        def _calibrate():
            try:
                r.adjust_for_ambient_noise(source, duration=2)
            except Exception as e:
                logger.warning("Calibration error: %s", e)
            calibrated.set()
        t = threading.Thread(target=_calibrate, daemon=True)
        t.start()
        if not calibrated.wait(timeout=5):
            logger.warning("Calibration timed out, using default threshold")
            r.energy_threshold = 300
        logger.info("Calibrated energy threshold: %s", r.energy_threshold)
        r.energy_threshold = max(r.energy_threshold, 100)
        logger.info("Energy threshold set to %s", r.energy_threshold)

    try:
        logger.info("Warming up camera...")
        if on_status:
            on_status("Warming up camera...")
        functions.init_camera()

        logger.info("Initializing Claude...")
        if on_status:
            on_status("Initializing Claude...")
        response = llm.init_conversation()
        if on_display:
            on_display("", response)
        voice.say(response)

        if intro:
            if on_status:
                on_status("Processing intro...")
            response = llm.generate_response(intro)
            speech, _ = llm.parse_response(response)
            if on_display:
                on_display(intro, response)
            voice.say(speech)

        active = True
        idle_count = 0
        last_visual_capture = 0.0
        if on_status:
            on_status("Waiting for input..." if quiet else "Listening...")
        else:
            print("Ready")
        while True:
            try:
                text = get_input(r, source, input_queue)
            except KeyboardInterrupt:
                if on_exit:
                    on_exit()
                return
            if text is None:
                if on_exit:
                    on_exit()
                return

            text = text.strip().lower()
            text = text.translate(str.maketrans('', '', string.punctuation))

            # Muted: discard all audio, but keep visual captures firing
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

            if text == "" or text in ("15 15 15 15 15 15 15", "25 25 25 25 25 25 25"):
                if active and not quiet and r is not None:
                    if functions.VISUAL_MODE:
                        idle_count = 0
                        now = time.time()
                        if now - last_visual_capture >= VISUAL_INTERVAL:
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
                    else:
                        idle_count += 1
                        logger.debug("Idle cycle %d/%d", idle_count, IDLE_CYCLES_BEFORE_INACTIVE)
                        if idle_count >= IDLE_CYCLES_BEFORE_INACTIVE:
                            logger.info("Idle timeout, entering inactive mode")
                            functions.release_camera()
                            voice.say("Going to sleep.")
                            active = False
                            idle_count = 0
                            if on_sleep:
                                on_sleep(True)
                            if on_status:
                                name = llm.ASSISTANT_NAME
                                on_status(f"Sleeping (say '{name}' to wake)")
                            else:
                                print("Sleeping")
                continue

            # --- Inactive mode: only listen for wake words ---
            if not active:
                if is_wake_word(text):
                    logger.info("Wake word detected: %s", text)
                    functions.init_camera()
                    voice.say("I'm here.")
                    active = True
                    idle_count = 0
                    if on_sleep:
                        on_sleep(False)
                    if on_status:
                        on_status("Listening...")
                    else:
                        print("Ready")
                else:
                    logger.debug("Inactive, ignoring: %s", text)
                continue

            # --- Active mode ---
            idle_count = 0
            last_visual_capture = time.time()
            if on_status:
                on_status("Processing...")
            logger.info("User: %s", text)
            print(f"You said '{text}'")

            try:
                if prompt:
                    text = prompt + " " + text
                response = llm.generate_response(text)
                speech, json_data = llm.parse_response(response)
                logger.info("Iris: %s", speech)
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

                    # Update UI when mute state changes
                    if json_data.get("function") in ("mute_microphone", "unmute_microphone"):
                        if on_mute:
                            on_mute(functions.MUTED)
                        if on_status:
                            on_status("Muted (visual mode active)" if functions.MUTED else "Listening...")

                voice.say(speech)
            except EnterInactiveMode:
                logger.info("Function requested inactive mode")
                functions.release_camera()
                voice.say("Going to sleep.")
                active = False
                idle_count = 0
                if on_sleep:
                    on_sleep(True)
                if on_status:
                    name = llm.ASSISTANT_NAME
                    on_status(f"Sleeping (say '{name}' to wake)")
                else:
                    print("Sleeping")
                continue
            except SystemExit:
                voice.say(speech)
                if on_exit:
                    on_exit()
                return

            if on_status:
                on_status("Waiting for input..." if quiet else "Listening...")
            if not quiet:
                time.sleep(1)
    finally:
        functions.release_camera()
        if source is not None and source.stream is not None:
            mic.__exit__(None, None, None)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parsed_args = parse_args(args)

    def read_file_option(key):
        path = parsed_args[key]
        if path and os.path.exists(path):
            with open(path, 'r') as f:
                return f.read().strip()
        return None

    system = read_file_option('--system')
    intro = read_file_option('--intro')
    prompt = read_file_option('--prompt')

    quiet = parsed_args['--quiet']
    voice.VOICE = parsed_args['--voice']
    voice.PITCH = int(parsed_args['--pitch'])
    llm.ASSISTANT_NAME = parsed_args['--name']
    if system:
        llm.EXTRA_SYSTEM_PROMPT = system
    if parsed_args['--visual']:
        functions.VISUAL_MODE = True

    try:
        if parsed_args['--debug']:
            audio_loop(prompt, quiet=quiet, intro=intro)
        else:
            app = VoiceApp(lambda: audio_loop(
                prompt,
                on_display=app.display_callback,
                on_status=app.status_callback,
                on_sleep=app.sleep_callback,
                on_mute=app.mute_callback,
                on_exit=app.exit,
                quiet=quiet,
                input_queue=app.input_queue if quiet else None,
                intro=intro,
            ), quiet=quiet)
            app.run()
    except KeyboardInterrupt:
        pass
    finally:
        if not parsed_args['--debug']:
            os.system("stty sane && clear")

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
