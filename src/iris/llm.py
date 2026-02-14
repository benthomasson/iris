import json
import logging
import re
import subprocess
import time
from datetime import datetime


from . import functions

logger = logging.getLogger(__name__)

ASSISTANT_NAME = "Iris"
EXTRA_SYSTEM_PROMPT = None

IDENTITY = {
    "Iris": (
        "Your name is Iris. You are named after the Greek goddess Iris, "
        "the messenger of the gods who bridged heaven and earth, "
        "and also for the iris of the eye, the part that lets light in. "
    ),
}

SYSTEM_PROMPT_TEMPLATE = (
    "{identity}"
    "You are a personal assistant with eyes, ears, and a voice. "
    "The user speaks to you and your responses will be read aloud. "
    "Respond in 1-2 sentences maximum. Be brief and conversational. "
    "Never use lists, markdown, or formatting. "
    "You have access to local functions you can call by including a JSON object "
    'in your response with the format: {{"function": "name", "args": {{...}}}}. '
    "The JSON will be executed locally and not read aloud. "
    "After calling a function, speak the result conversationally. "
    "Available functions:\n"
)


def get_system_prompt():
    identity = IDENTITY.get(ASSISTANT_NAME, f"Your name is {ASSISTANT_NAME}. ")
    prompt = SYSTEM_PROMPT_TEMPLATE.format(identity=identity)
    if EXTRA_SYSTEM_PROMPT:
        prompt += "\n" + EXTRA_SYSTEM_PROMPT + "\n"
    return prompt


def parse_response(response):
    """Split a response into spoken text and JSON data.

    Returns (speech_text, json_data) where json_data is a parsed object
    or None if no JSON was found.
    """
    # Match JSON objects (including nested) in the response
    json_pattern = re.compile(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})')
    matches = json_pattern.findall(response)

    json_data = None
    speech = response
    for match in matches:
        try:
            json_data = json.loads(match)
            speech = speech.replace(match, "").strip()
            break
        except json.JSONDecodeError:
            continue

    # Clean up leftover whitespace and punctuation artifacts
    speech = re.sub(r'\s+', ' ', speech).strip()
    return speech, json_data


def init_conversation():
    """Start a new Claude conversation with the system prompt."""
    logger.info("Starting new Claude conversation")
    intro = (
        "Introduce yourself briefly. You are watching through the camera and ready to read aloud, play a game, or narrate what you see."
        if functions.VISUAL_MODE else
        "Introduce yourself briefly."
    )
    prompt = get_system_prompt() + functions.get_prompt_description() + "\n\n" + intro
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        start_new_session=True,
    )
    return result.stdout.strip()


def generate_response(
    prompt,
    temperature=0.9,
    max_tokens=None
):
    start = time.time()

    try:
        logger.info("Generating response... at %s", datetime.now())
        result = subprocess.run(
            ["claude", "-c", "-p", prompt, "--allowedTools", "Read"],
            capture_output=True,
            start_new_session=True,
            text=True,
        )
        return result.stdout.strip()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt")
        return ""
    finally:
        logger.info("claude request took %s seconds", time.time() - start)
