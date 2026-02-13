import logging
import subprocess
import time
from datetime import datetime


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are part of a computer voice interface. "
    "The user speaks to you and your responses will be read aloud. "
    "Keep responses concise and conversational."
)


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
