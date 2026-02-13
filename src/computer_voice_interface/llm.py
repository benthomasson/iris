import json
import logging
import re
import subprocess
import time
from datetime import datetime


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are part of a computer voice interface. "
    "The user speaks to you and your responses will be read aloud. "
    "Respond in 1-2 sentences maximum. Be brief and conversational. "
    "Never use lists, markdown, or formatting. "
    "When you want to return structured data, include a JSON object "
    "in your response. The JSON will be shown on screen but not read aloud."
)


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
    result = subprocess.run(
        ["claude", "-p", SYSTEM_PROMPT + " Say hello."],
        capture_output=True,
        text=True,
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
            ["claude", "-c", "-p", prompt],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt")
        return ""
    finally:
        logger.info("claude request took %s seconds", time.time() - start)
