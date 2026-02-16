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
    --passive               Start in passive mode (listen, respond only when addressed)
    --dictate               Start in dictation mode (transcribe to file, query on wake)
    --no-shutter            Disable camera shutter sound
    --no-camera             Skip camera initialization
    --message=<contacts>    Message mode: respond via iMessage to named contacts (comma-separated)
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
import threading
from . import functions
from .functions import EnterInactiveMode
from . import llm
from . import voice
from .ui import VoiceApp

IDLE_CYCLES_BEFORE_INACTIVE = 25  # ~125s of silence with 5s listen timeout
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


def _execute_functions(json_list):
    """Execute a list of function calls, return list of (name, result) tuples.

    Raises EnterInactiveMode or SystemExit if any function triggers them.
    """
    results = []
    for json_data in json_list:
        name = json_data["function"]
        args = json_data.get("args", {})
        result = functions.call(name, args)
        results.append((name, result))
    return results


def _build_follow_up(results):
    """Build a follow-up prompt summarizing all function results."""
    parts = []
    image_path = None
    for name, result in results:
        path = result.get("path", "") if isinstance(result, dict) else ""
        if path and path.endswith(".png"):
            image_path = path
        parts.append(f"{name} returned: {json.dumps(result)}")
    if image_path and len(results) == 1:
        return (
            f"Read the image at {image_path} and describe what you see. "
            "Be brief and conversational."
        )
    return "Functions called:\n" + "\n".join(parts) + "\nSummarize the results conversationally."


def _generate_with_timer(prompt_text, on_status=None):
    """Run llm.generate_response with an elapsed-time counter on the status bar."""
    if not on_status:
        return llm.generate_response(prompt_text)
    result = [None]

    def _run():
        result[0] = llm.generate_response(prompt_text)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    elapsed = 0
    while t.is_alive():
        t.join(timeout=1)
        if t.is_alive():
            elapsed += 1
            on_status(f"Processing... ({elapsed}s)")
    return result[0]


def _listen_with_watchdog(r, source, timeout, phrase_limit, on_status=None):
    """Run r.listen() in a thread with a hard watchdog timeout."""
    result = [None]
    error = [None]

    def _listen():
        try:
            result[0] = r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=_listen, daemon=True)
    t.start()
    watchdog = timeout + phrase_limit + 10
    elapsed = 0
    while elapsed < watchdog:
        t.join(timeout=1)
        if not t.is_alive():
            break
        elapsed += 1
        remaining = max(0, watchdog - elapsed)
        if on_status:
            on_status(f"Listening... ({remaining}s)")
    if t.is_alive():
        raise OSError(f"Microphone hung (no response in {watchdog}s)")
    if error[0] is not None:
        raise error[0]
    return result[0]


def recognize_audio(r, source, on_status=None):
    try:
        timeout = 3 if functions.VISUAL_MODE else 5
        phrase_limit = 3 if functions.VISUAL_MODE else 30
        logger.debug("Listening... (energy_threshold=%s)", r.energy_threshold)
        audio_data = _listen_with_watchdog(r, source, timeout, phrase_limit, on_status=on_status)
        duration = len(audio_data.frame_data) / (audio_data.sample_rate * audio_data.sample_width)
        logger.info("Captured %.1fs of audio (threshold=%s)", duration, r.energy_threshold)
        if duration < 0.5:
            logger.debug("Audio too short (%.1fs), skipping recognition", duration)
            return ""
        text = r.recognize_whisper(audio_data)
    except sr.WaitTimeoutError:
        logger.debug("Listen timed out waiting for speech")
        text = ""
    except OSError as e:
        logger.error("Microphone error: %s", e)
        return None
    except Exception as e:
        logger.error("Audio capture failed: %s", e)
        return None
    return text


def get_input(r=None, source=None, input_queue=None, on_status=None):
    """Get user input from mic, stdin, or TUI queue."""
    if input_queue is not None:
        return input_queue.get()
    if r is None:
        try:
            return input("> ")
        except (EOFError, KeyboardInterrupt):
            return None
    return recognize_audio(r, source, on_status=on_status)


def _edit_distance(a, b):
    """Damerau-Levenshtein distance (transpositions count as 1 edit)."""
    len_a, len_b = len(a), len(b)
    d = [[0] * (len_b + 1) for _ in range(len_a + 1)]
    for i in range(len_a + 1):
        d[i][0] = i
    for j in range(len_b + 1):
        d[0][j] = j
    for i in range(1, len_a + 1):
        for j in range(1, len_b + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len_a][len_b]


def is_wake_word(text):
    """Check if text contains a wake word to exit inactive mode."""
    name = llm.ASSISTANT_NAME.lower()
    words = text.lower().split()
    if any(_edit_distance(w, name) <= 1 for w in words):
        return True
    if "wake" in words and "up" in words:
        return True
    return False


def audio_loop(prompt=None, on_display=None, on_status=None, on_sleep=None,
               on_mute=None, on_exit=None, quiet=False, input_queue=None, intro=None,
               no_camera=False):
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
        if not no_camera:
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
            response = _generate_with_timer(intro, on_status=on_status)
            speech, _ = llm.parse_response(response)
            if on_display:
                on_display(intro, response)
            voice.say(speech)

        active = True
        idle_count = 0
        last_visual_capture = 0.0
        passive_buffer = []
        if on_status:
            if functions.DICTATION_MODE:
                on_status(f"Dictating ({functions._dictation_line_count} lines)")
            elif functions.PASSIVE_MODE:
                on_status("Passive mode (0 lines)")
            else:
                on_status("Waiting for input..." if quiet else "Listening...")
        else:
            print("Ready")
        while True:
            try:
                text = get_input(r, source, input_queue, on_status=on_status)
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

            # Muted: discard all audio unless it contains "unmute"
            if functions.MUTED and r is not None and not quiet:
                if not (text and "unmute" in text.split()):
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
                            response = _generate_with_timer(prompt_text, on_status=on_status)
                            speech, _ = llm.parse_response(response)
                            if on_display:
                                on_display("[visual]", response)
                            voice.say(speech)
                    continue

            # Passive mode: buffer speech, only send to Claude on wake word
            if functions.PASSIVE_MODE and active and r is not None and not quiet:
                if text:
                    passive_buffer.append(text)
                    if on_status:
                        on_status(f"Passive mode ({len(passive_buffer)} lines)")
                if text and is_wake_word(text):
                    # Addressed by name — send buffer as context
                    context = "\n".join(passive_buffer)
                    passive_buffer.clear()
                    prompt_text = (
                        f"You have been in passive mode, listening to a conversation. "
                        f"Here is what you overheard:\n\n{context}\n\n"
                        f"Someone just addressed you directly. Respond to them."
                    )
                    if on_status:
                        on_status("Processing...")
                    response = _generate_with_timer(prompt_text, on_status=on_status)
                    speech, json_list = llm.parse_response(response)
                    if on_display:
                        on_display(f"[conversation] {text}", response)
                    # Handle function calls same as active mode
                    if json_list:
                        voice.say(speech)
                        results = _execute_functions(json_list)
                        follow_up_prompt = _build_follow_up(results)
                        follow_up = _generate_with_timer(follow_up_prompt, on_status=on_status)
                        speech, _ = llm.parse_response(follow_up)
                        if on_display:
                            on_display(text, follow_up)
                        # Clear buffer and update status after toggling passive mode off
                        called = {jd["function"] for jd in json_list}
                        if "stop_passive_mode" in called:
                            passive_buffer.clear()
                            if on_status:
                                on_status("Listening...")
                            voice.say(speech)
                            continue
                    voice.say(speech)
                    if on_status:
                        on_status(f"Passive mode (0 lines)")
                else:
                    # No wake word — keep visual captures firing if enabled
                    now = time.time()
                    if functions.VISUAL_MODE and now - last_visual_capture >= VISUAL_INTERVAL:
                        last_visual_capture = now
                        result = functions.capture_image()
                        if isinstance(result, dict) and "path" in result:
                            prompt_text = (
                                f"Read the image at {result['path']} and describe what you see. "
                                "Narrate any changes or interesting details briefly."
                            )
                            response = _generate_with_timer(prompt_text, on_status=on_status)
                            speech, _ = llm.parse_response(response)
                            if on_display:
                                on_display("[visual]", response)
                            voice.say(speech)
                idle_count = 0  # suppress auto-sleep
                continue

            # Dictation mode: transcribe to disk, send to Claude on wake word
            if functions.DICTATION_MODE and active and r is not None and not quiet:
                if text and text not in ("15 15 15 15 15 15 15", "25 25 25 25 25 25 25"):
                    functions.append_dictation(text)
                    if on_status:
                        on_status(f"Dictating ({functions._dictation_line_count} lines)")
                if text and is_wake_word(text):
                    context = functions.get_dictation_context(max_lines=100)
                    prompt_text = (
                        f"You are in dictation mode, continuously transcribing speech to a file. "
                        f"Here is the recent transcript:\n\n{context}\n\n"
                        f"Someone just addressed you. Respond to their request. "
                        f"You can summarize, answer questions about the transcript, or save structured notes. "
                        f"The transcript will continue accumulating after you respond."
                    )
                    if on_status:
                        on_status("Processing...")
                    response = _generate_with_timer(prompt_text, on_status=on_status)
                    speech, json_list = llm.parse_response(response)
                    if on_display:
                        on_display(f"[dictation] {text}", response)
                    if json_list:
                        voice.say(speech)
                        results = _execute_functions(json_list)
                        follow_up_prompt = _build_follow_up(results)
                        follow_up = _generate_with_timer(follow_up_prompt, on_status=on_status)
                        speech, _ = llm.parse_response(follow_up)
                        if on_display:
                            on_display(text, follow_up)
                        called = {jd["function"] for jd in json_list}
                        if "stop_dictation" in called:
                            voice.say(speech)
                            if on_status:
                                on_status("Listening...")
                            continue
                    voice.say(speech)
                    if on_status:
                        on_status(f"Dictating ({functions._dictation_line_count} lines)")
                else:
                    now = time.time()
                    if functions.VISUAL_MODE and now - last_visual_capture >= VISUAL_INTERVAL:
                        last_visual_capture = now
                        result = functions.capture_image()
                        if isinstance(result, dict) and "path" in result:
                            prompt_text = (
                                f"Read the image at {result['path']} and describe what you see. "
                                "Narrate any changes or interesting details briefly."
                            )
                            response = _generate_with_timer(prompt_text, on_status=on_status)
                            speech, _ = llm.parse_response(response)
                            if on_display:
                                on_display("[visual]", response)
                            voice.say(speech)
                idle_count = 0  # suppress auto-sleep
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
                                response = _generate_with_timer(prompt_text, on_status=on_status)
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
                response = _generate_with_timer(text, on_status=on_status)
                speech, json_list = llm.parse_response(response)
                logger.info("Iris: %s", speech)
                if on_display:
                    on_display(text, response)
                if json_list:
                    for jd in json_list:
                        print(json.dumps(jd, indent=2))

                # If Claude called functions, speak initial text, then execute all
                if json_list:
                    voice.say(speech)
                    results = _execute_functions(json_list)
                    for name, result in results:
                        print(json.dumps(result, indent=2))
                    follow_up_prompt = _build_follow_up(results)
                    follow_up = _generate_with_timer(follow_up_prompt, on_status=on_status)
                    speech, _ = llm.parse_response(follow_up)
                    if on_display:
                        on_display(text, follow_up)

                    # Update UI based on which functions were called
                    called = {jd["function"] for jd in json_list}
                    if called & {"mute_microphone", "unmute_microphone"}:
                        if on_mute:
                            on_mute(functions.MUTED)
                        if on_status:
                            on_status("Muted (visual mode active)" if functions.MUTED else "Listening...")

                    if called & {"start_passive_mode", "stop_passive_mode"}:
                        if not functions.PASSIVE_MODE:
                            passive_buffer.clear()
                        if on_status:
                            if functions.PASSIVE_MODE:
                                on_status("Passive mode (0 lines)")
                            else:
                                on_status("Listening...")

                    if called & {"start_dictation", "stop_dictation"}:
                        if functions.DICTATION_MODE:
                            passive_buffer.clear()
                        if on_status:
                            if functions.DICTATION_MODE:
                                on_status(f"Dictating ({functions._dictation_line_count} lines)")
                            else:
                                on_status("Listening...")

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
        if functions.DICTATION_MODE:
            functions.stop_dictation()
        functions.release_camera()
        if source is not None and source.stream is not None:
            mic.__exit__(None, None, None)


def _poll_new_messages(handles, last_rowid):
    """Poll chat.db for new incoming messages from the given handles since last_rowid."""
    import subprocess as sp
    handle_list = ",".join(f"'{h}'" for h in handles)
    sql = (
        f"SELECT message.ROWID, message.text, handle.id as sender "
        f"FROM message "
        f"JOIN handle ON message.handle_id = handle.ROWID "
        f"WHERE message.ROWID > {last_rowid} "
        f"AND message.is_from_me = 0 "
        f"AND message.text IS NOT NULL "
        f"AND handle.id IN ({handle_list}) "
        f"ORDER BY message.date ASC;"
    )
    chat_db = str(functions._CHAT_DB)
    result = sp.run(
        ["sqlite3", "-json", chat_db, sql],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return json.loads(result.stdout.strip())


def _get_max_rowid():
    """Get the current maximum message ROWID from chat.db."""
    import subprocess as sp
    chat_db = str(functions._CHAT_DB)
    result = sp.run(
        ["sqlite3", chat_db, "SELECT MAX(ROWID) FROM message;"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def message_loop(contacts_str, prompt=None, intro=None, no_camera=False):
    """Main loop for message mode: poll iMessages and respond via iMessage."""
    voice.QUIET = True
    llm.MESSAGE_MODE = True

    # Resolve contact names to handles
    contact_names = [c.strip() for c in contacts_str.split(",") if c.strip()]
    handles = {}  # handle -> contact name
    for name in contact_names:
        try:
            handle = functions._resolve_recipient(name)
            handles[handle] = name
            logger.info("Resolved '%s' -> %s", name, handle)
            print(f"Monitoring: {name} ({handle})")
        except RuntimeError as e:
            logger.error("Could not resolve '%s': %s", name, e)
            print(f"Error: Could not resolve '{name}': {e}")
            return

    if not handles:
        print("No contacts to monitor.")
        return

    # Initialize camera and Claude
    if not no_camera:
        logger.info("Warming up camera...")
        functions.init_camera()

    logger.info("Initializing Claude...")
    response = llm.init_conversation()
    logger.info("Claude: %s", response)

    # Notify contacts that Iris is online
    for handle, name in handles.items():
        functions._send_imessage_to_handle(handle, f"Hi, {llm.ASSISTANT_NAME} is online.")
        logger.info("Sent online notification to %s (%s)", name, handle)

    # Start polling from current max ROWID (only respond to new messages)
    last_rowid = _get_max_rowid()
    logger.info("Starting message poll from ROWID %d", last_rowid)
    print(f"Message mode active. Polling for new messages... (Ctrl-C to quit)")

    try:
        while True:
            new_messages = _poll_new_messages(list(handles.keys()), last_rowid)

            for msg in new_messages:
                rowid = msg["ROWID"]
                text = msg["text"]
                sender = msg["sender"]
                contact_name = handles.get(sender, sender)
                last_rowid = max(last_rowid, rowid)

                logger.info("Message from %s (%s): %s", contact_name, sender, text)
                print(f"\n[{contact_name}] {text}")

                try:
                    prompt_text = f"[Message from {contact_name}] {text}"
                    if prompt:
                        prompt_text = prompt + " " + prompt_text
                    response = llm.generate_response(prompt_text)
                    speech, json_list = llm.parse_response(response)
                    logger.info("Iris: %s", response)

                    # Handle function calls
                    if json_list:
                        for jd in json_list:
                            logger.info("Calling function: %s(%s)",
                                        jd["function"], jd.get("args", {}))
                        try:
                            results = _execute_functions(json_list)
                        except EnterInactiveMode:
                            logger.info("Sleep requested in message mode, ignoring")
                            results = [("go_to_sleep", {"status": "sleep not available in message mode"})]
                        except SystemExit:
                            print(f"  -> {speech}")
                            if speech:
                                functions._send_imessage_to_handle(sender, speech)
                            return

                        for name, result in results:
                            print(f"  [fn] {name} -> {json.dumps(result)}")
                        follow_up_prompt = _build_follow_up(results)
                        follow_up = llm.generate_response(follow_up_prompt)
                        speech, _ = llm.parse_response(follow_up)

                    if speech:
                        print(f"  -> {speech}")
                        send_result = functions._send_imessage_to_handle(sender, speech)
                        if send_result is not True:
                            logger.error("Failed to send reply: %s", send_result)
                            print(f"  [error] Failed to send: {send_result}")
                    else:
                        logger.warning("Empty response, not sending")

                except Exception as e:
                    logger.error("Error processing message: %s", e)
                    print(f"  [error] {e}")

            time.sleep(2)
    except KeyboardInterrupt:
        print("\nMessage mode stopped.")
    finally:
        functions.release_camera()


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
    if parsed_args['--no-shutter']:
        functions.SHUTTER_SOUND = False
    if parsed_args['--passive']:
        functions.PASSIVE_MODE = True
    if parsed_args['--dictate']:
        functions.start_dictation()

    no_camera = parsed_args['--no-camera']

    if parsed_args['--message']:
        try:
            message_loop(parsed_args['--message'], prompt=prompt, intro=intro,
                         no_camera=no_camera)
        except KeyboardInterrupt:
            pass
        return 0

    try:
        if parsed_args['--debug']:
            audio_loop(prompt, quiet=quiet, intro=intro, no_camera=no_camera)
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
                no_camera=no_camera,
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
