"""Local functions that Claude can call via JSON blocks."""

import logging
import os
import platform
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
import urllib.parse
import json
from datetime import datetime
from pathlib import Path
from . import voice

logger = logging.getLogger(__name__)

FUNCTION_REGISTRY = {}

VISUAL_MODE = False
MUTED = False
PASSIVE_MODE = False
DICTATION_MODE = False
SHUTTER_SOUND = True

DICTATION_DIR = Path.home() / ".iris" / "dictation"
_dictation_file = None
_dictation_path = None
_dictation_line_count = 0
_dictation_start_time = None


class EnterInactiveMode(Exception):
    """Raised by go_to_sleep to signal the main loop to enter inactive mode."""
    pass


def register(name, description, parameters):
    """Decorator to register a function Claude can call."""
    def decorator(fn):
        FUNCTION_REGISTRY[name] = {
            "function": fn,
            "description": description,
            "parameters": parameters,
        }
        return fn
    return decorator


def call(name, args):
    """Call a registered function by name with the given args dict."""
    if name not in FUNCTION_REGISTRY:
        return {"error": f"Unknown function: {name}"}
    try:
        return FUNCTION_REGISTRY[name]["function"](**args)
    except (EnterInactiveMode, SystemExit):
        raise
    except Exception as e:
        return {"error": str(e)}


def get_prompt_description():
    """Generate a description of available functions for the system prompt."""
    lines = []
    for name, info in FUNCTION_REGISTRY.items():
        params = ", ".join(
            f'{p["name"]} ({p["type"]}): {p["description"]}'
            for p in info["parameters"]
        )
        lines.append(f'- {name}({params}): {info["description"]}')
    return "\n".join(lines)


# --- Registered functions ---


@register(
    name="get_weather",
    description="Get the current weather for a location",
    parameters=[
        {"name": "location", "type": "string", "description": "City or location name"},
    ],
)
def get_weather(location):
    """Get real weather using Open-Meteo (no API key needed)."""
    try:
        # Geocode the location name to lat/lon (use just the city name)
        city = location.split(",")[0].strip()
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode({
            "name": city, "count": 1
        })
        with urllib.request.urlopen(geo_url) as resp:
            geo = json.loads(resp.read())

        if "results" not in geo or not geo["results"]:
            return {"error": f"Could not find location: {location}"}

        place = geo["results"][0]
        lat, lon = place["latitude"], place["longitude"]
        name = place.get("name", location)

        # Fetch current weather
        weather_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "temperature_unit": "celsius",
        })
        with urllib.request.urlopen(weather_url) as resp:
            weather = json.loads(resp.read())

        current = weather["current"]
        # Map WMO weather codes to descriptions
        code = current["weather_code"]
        conditions = {
            0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "depositing rime fog",
            51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
            61: "slight rain", 63: "moderate rain", 65: "heavy rain",
            71: "slight snow", 73: "moderate snow", 75: "heavy snow",
            80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
            95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
        }
        return {
            "location": name,
            "temperature_c": current["temperature_2m"],
            "humidity_pct": current["relative_humidity_2m"],
            "condition": conditions.get(code, f"code {code}"),
            "wind_speed_kmh": current["wind_speed_10m"],
        }
    except Exception as e:
        logger.error("Weather lookup failed: %s", e)
        return {"error": str(e)}


# --- Time & Date ---


@register(
    name="get_time",
    description="Get the current time and date",
    parameters=[],
)
def get_time():
    now = datetime.now()
    return {
        "time": now.strftime("%I:%M %p"),
        "date": now.strftime("%A, %B %d, %Y"),
    }


# --- Timer ---

NOTES_DIR = Path.home() / ".cvi_notes"

_active_timers = []  # list of {"label", "cancel"} dicts


@register(
    name="set_timer",
    description="Set a countdown timer that announces when done",
    parameters=[
        {"name": "seconds", "type": "number", "description": "Number of seconds for the timer"},
        {"name": "label", "type": "string", "description": "What the timer is for"},
    ],
)
def set_timer(seconds, label="timer"):
    cancelled = threading.Event()

    def _timer():
        if not cancelled.wait(seconds):
            voice.say(f"Timer done: {label}")
        _active_timers[:] = [t for t in _active_timers if not t["cancel"].is_set()]

    entry = {"label": label, "cancel": cancelled}
    _active_timers.append(entry)
    threading.Thread(target=_timer, daemon=True).start()
    return {"status": "started", "seconds": seconds, "label": label}


@register(
    name="cancel_last_timer",
    description="Cancel the most recently set timer",
    parameters=[],
)
def cancel_last_timer():
    for timer in reversed(_active_timers):
        if not timer["cancel"].is_set():
            timer["cancel"].set()
            return {"status": "cancelled", "label": timer["label"]}
    return {"error": "No active timers"}


@register(
    name="cancel_all_timers",
    description="Cancel all active timers",
    parameters=[],
)
def cancel_all_timers():
    cancelled = []
    for timer in _active_timers:
        if not timer["cancel"].is_set():
            timer["cancel"].set()
            cancelled.append(timer["label"])
    _active_timers.clear()
    if cancelled:
        return {"status": "cancelled", "labels": cancelled}
    return {"error": "No active timers"}


# --- Calculator ---


@register(
    name="calculate",
    description="Evaluate a math expression and return the result",
    parameters=[
        {"name": "expression", "type": "string", "description": "Math expression to evaluate, e.g. '347 * 23'"},
    ],
)
def calculate(expression):
    # Only allow safe math characters
    allowed = set("0123456789+-*/.() %")
    if not all(c in allowed for c in expression):
        return {"error": "Invalid characters in expression"}
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}


# --- System Info ---


@register(
    name="get_system_info",
    description="Get system information like disk space, IP address, and uptime",
    parameters=[],
)
def get_system_info():
    disk = shutil.disk_usage("/")
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "unknown"
    return {
        "hostname": socket.gethostname(),
        "ip_address": ip,
        "os": f"{platform.system()} {platform.release()}",
        "disk_free_gb": round(disk.free / (1024 ** 3), 1),
        "disk_total_gb": round(disk.total / (1024 ** 3), 1),
    }


# --- Notes/Reminders ---


@register(
    name="save_note",
    description="Save a note or reminder to retrieve later",
    parameters=[
        {"name": "text", "type": "string", "description": "The note or reminder text"},
    ],
)
def save_note(text):
    NOTES_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = NOTES_DIR / f"{timestamp}.txt"
    path.write_text(text)
    return {"status": "saved", "note": text}


@register(
    name="get_notes",
    description="Retrieve all saved notes and reminders",
    parameters=[],
)
def get_notes():
    if not NOTES_DIR.exists():
        return {"notes": []}
    now = datetime.now()
    notes = []
    for f in sorted(NOTES_DIR.glob("*.txt")):
        created = datetime.strptime(f.stem, "%Y%m%d_%H%M%S")
        delta = now - created
        if delta.days > 0:
            ago = f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.seconds >= 60:
            mins = delta.seconds // 60
            ago = f"{mins} minute{'s' if mins != 1 else ''} ago"
        else:
            ago = "just now"
        notes.append({"timestamp": f.stem, "ago": ago, "text": f.read_text()})
    return {"notes": notes}


# --- Wikipedia ---


@register(
    name="wikipedia_summary",
    description="Get a short summary about a topic from Wikipedia",
    parameters=[
        {"name": "topic", "type": "string", "description": "Topic to look up"},
    ],
)
def wikipedia_summary(topic):
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(topic)
        req = urllib.request.Request(url, headers={"User-Agent": "CVI/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return {"title": data.get("title", topic), "summary": data.get("extract", "No summary available.")}
    except Exception as e:
        logger.error("Wikipedia lookup failed: %s", e)
        return {"error": str(e)}


# --- Unit Conversion ---


@register(
    name="convert_units",
    description="Convert between common units (distance, weight, temperature)",
    parameters=[
        {"name": "value", "type": "number", "description": "The numeric value to convert"},
        {"name": "from_unit", "type": "string", "description": "Unit to convert from"},
        {"name": "to_unit", "type": "string", "description": "Unit to convert to"},
    ],
)
def convert_units(value, from_unit, to_unit):
    conversions = {
        ("miles", "km"): lambda v: v * 1.60934,
        ("km", "miles"): lambda v: v / 1.60934,
        ("pounds", "kg"): lambda v: v * 0.453592,
        ("kg", "pounds"): lambda v: v / 0.453592,
        ("fahrenheit", "celsius"): lambda v: (v - 32) * 5 / 9,
        ("celsius", "fahrenheit"): lambda v: v * 9 / 5 + 32,
        ("feet", "meters"): lambda v: v * 0.3048,
        ("meters", "feet"): lambda v: v / 0.3048,
        ("inches", "cm"): lambda v: v * 2.54,
        ("cm", "inches"): lambda v: v / 2.54,
        ("gallons", "liters"): lambda v: v * 3.78541,
        ("liters", "gallons"): lambda v: v / 3.78541,
        ("ounces", "grams"): lambda v: v * 28.3495,
        ("grams", "ounces"): lambda v: v / 28.3495,
    }
    key = (from_unit.lower(), to_unit.lower())
    if key not in conversions:
        return {"error": f"Cannot convert from {from_unit} to {to_unit}"}
    result = conversions[key](value)
    return {"value": value, "from": from_unit, "to": to_unit, "result": round(result, 4)}


# --- Vision ---

_camera = None


def init_camera():
    """Open the webcam and warm it up. Call at startup."""
    global _camera
    import cv2
    _camera = cv2.VideoCapture(0)
    if not _camera.isOpened():
        logger.error("Could not open webcam")
        _camera = None
        return False
    # Warm up auto-exposure
    for _ in range(30):
        _camera.read()
    logger.info("Camera ready")
    return True


def release_camera():
    """Release the webcam."""
    global _camera
    if _camera is not None:
        _camera.release()
        _camera = None


@register(
    name="capture_image",
    description="Capture a photo from the webcam",
    parameters=[],
)
def capture_image():
    if _camera is None or not _camera.isOpened():
        return {"error": "Camera not available"}
    ret, frame = _camera.read()
    if not ret:
        return {"error": "Could not capture frame"}
    if SHUTTER_SOUND:
        subprocess.Popen(
            ["afplay", "/System/Library/Sounds/Tink.aiff"],
            start_new_session=True,
        )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path.home() / ".iris" / "captures"
    path.mkdir(parents=True, exist_ok=True)
    filepath = path / f"{timestamp}.png"
    import cv2
    cv2.imwrite(str(filepath), frame)
    return {"status": "captured", "path": str(filepath)}


# --- Stubs (not yet implemented) ---


@register(
    name="home_automation",
    description="Control smart home devices (not yet connected)",
    parameters=[
        {"name": "device", "type": "string", "description": "Device name, e.g. 'living room lights'"},
        {"name": "action", "type": "string", "description": "Action to perform, e.g. 'on', 'off', 'dim 50%'"},
    ],
)
def home_automation(device, action):
    # TODO: Connect to Home Assistant or similar
    return {"status": "not_implemented", "message": f"Home automation not yet connected. Would {action} {device}."}


@register(
    name="play_music",
    description="Play music or a podcast (not yet connected)",
    parameters=[
        {"name": "query", "type": "string", "description": "Song, artist, playlist, or podcast name"},
    ],
)
def play_music(query):
    # TODO: Connect to Spotify, Apple Music, etc.
    return {"status": "not_implemented", "message": f"Music playback not yet connected. Would play: {query}"}


@register(
    name="send_message",
    description="Send a message to someone (not yet connected)",
    parameters=[
        {"name": "recipient", "type": "string", "description": "Who to send the message to"},
        {"name": "message", "type": "string", "description": "The message content"},
    ],
)
def send_message(recipient, message):
    # TODO: Connect to iMessage, Slack, etc.
    return {"status": "not_implemented", "message": f"Messaging not yet connected. Would send to {recipient}: {message}"}


# --- System Control ---


@register(
    name="start_visual_mode",
    description="Start visual mode to periodically capture and describe what the camera sees. Use when user says 'start watching', 'watch this', 'look at this', etc.",
    parameters=[],
)
def start_visual_mode():
    global VISUAL_MODE
    VISUAL_MODE = True
    return {"status": "visual_mode_enabled"}


@register(
    name="stop_visual_mode",
    description="Stop visual mode. Use when user says 'stop watching', 'stop looking', etc.",
    parameters=[],
)
def stop_visual_mode():
    global VISUAL_MODE
    VISUAL_MODE = False
    return {"status": "visual_mode_disabled"}


@register(
    name="mute_microphone",
    description="Mute the microphone. Use when user says 'mute', 'mute mic', 'stop listening but keep watching', etc. Visual mode continues working.",
    parameters=[],
)
def mute_microphone():
    global MUTED
    MUTED = True
    return {"status": "microphone_muted"}


@register(
    name="unmute_microphone",
    description="Unmute the microphone. Use when user says 'unmute', 'unmute mic', 'start listening again', etc.",
    parameters=[],
)
def unmute_microphone():
    global MUTED
    MUTED = False
    return {"status": "microphone_unmuted"}


@register(
    name="start_passive_mode",
    description="Start passive mode. Iris listens passively and only responds when addressed by name. Use when user says 'passive mode', 'just listen', 'listen in', etc.",
    parameters=[],
)
def start_passive_mode():
    global PASSIVE_MODE
    PASSIVE_MODE = True
    return {"status": "passive_mode_enabled"}


@register(
    name="stop_passive_mode",
    description="Stop passive mode and return to normal listening. Use when user says 'stop passive mode', 'normal mode', 'stop listening passively', etc.",
    parameters=[],
)
def stop_passive_mode():
    global PASSIVE_MODE
    PASSIVE_MODE = False
    return {"status": "passive_mode_disabled"}


# --- Dictation Mode ---


def append_dictation(text):
    """Write a timestamped line to the dictation file and flush."""
    global _dictation_line_count
    if _dictation_file is None:
        return
    timestamp = datetime.now().strftime("%H:%M:%S")
    _dictation_file.write(f"[{timestamp}] {text}\n")
    _dictation_file.flush()
    _dictation_line_count += 1


def get_dictation_context(max_lines=100):
    """Read the last N lines from the dictation file for the wake word prompt."""
    if _dictation_path is None or not _dictation_path.exists():
        return "(no transcript yet)"
    lines = _dictation_path.read_text().splitlines()
    total = len(lines)
    recent = lines[-max_lines:]
    header = f"[Dictation transcript: {total} total lines, started {_dictation_start_time}]"
    if total > max_lines:
        header += f"\n[...showing last {max_lines} of {total} lines...]"
    return header + "\n" + "\n".join(recent)


@register(
    name="start_dictation",
    description="Start dictation mode. Speech is transcribed to a file on disk. Responds only when addressed by name. Use when user says 'start dictation', 'take notes', 'record this meeting', etc.",
    parameters=[],
)
def start_dictation():
    global DICTATION_MODE, PASSIVE_MODE, _dictation_file, _dictation_path
    global _dictation_line_count, _dictation_start_time
    DICTATION_MODE = True
    PASSIVE_MODE = False
    DICTATION_DIR.mkdir(parents=True, exist_ok=True)
    _dictation_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = datetime.now().strftime("%Y%m%d_%H%M%S.txt")
    _dictation_path = DICTATION_DIR / filename
    _dictation_file = open(_dictation_path, "a")
    _dictation_line_count = 0
    return {"status": "dictation_started", "path": str(_dictation_path)}


@register(
    name="stop_dictation",
    description="Stop dictation mode and close the transcript file. Use when user says 'stop dictation', 'stop recording', 'end transcription', etc.",
    parameters=[],
)
def stop_dictation():
    global DICTATION_MODE, _dictation_file, _dictation_path
    global _dictation_line_count, _dictation_start_time
    DICTATION_MODE = False
    path = str(_dictation_path) if _dictation_path else None
    count = _dictation_line_count
    if _dictation_file is not None:
        _dictation_file.close()
        _dictation_file = None
    result = {"status": "dictation_stopped", "lines": count}
    if path:
        result["path"] = path
    _dictation_path = None
    _dictation_line_count = 0
    _dictation_start_time = None
    return result


@register(
    name="get_dictation_transcript",
    description="Read a portion of the current dictation transcript. Use to review what has been said.",
    parameters=[
        {"name": "lines", "type": "number", "description": "Number of lines to return (default 50)"},
        {"name": "offset", "type": "number", "description": "Number of lines to skip from the end (0 = most recent)"},
    ],
)
def get_dictation_transcript(lines=50, offset=0):
    if _dictation_path is None or not _dictation_path.exists():
        return {"error": "No active dictation transcript"}
    all_lines = _dictation_path.read_text().splitlines()
    total = len(all_lines)
    if offset > 0:
        selected = all_lines[-(offset + lines):-offset] if offset + lines <= total else all_lines[:max(0, total - offset)]
    else:
        selected = all_lines[-lines:]
    return {"total_lines": total, "returned": len(selected), "offset": offset, "lines": selected}


@register(
    name="go_to_sleep",
    description="Enter sleep/inactive mode. Use when the user says 'pause', 'take a break', 'go to sleep', 'stop listening', or similar. The assistant will stop processing until woken by name.",
    parameters=[],
)
def go_to_sleep():
    raise EnterInactiveMode


@register(
    name="shutdown",
    description="Shut down the voice interface. Use when the user says goodbye or asks to shut down.",
    parameters=[],
)
def shutdown():
    raise SystemExit
