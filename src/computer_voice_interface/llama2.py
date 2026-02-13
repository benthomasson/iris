import logging
import time
from datetime import datetime

import ollama

model_engine = "llama3"


logger = logging.getLogger(__name__)


def generate_response(
    prompt,
    temperature=0.9,
    max_tokens=None
):
    start = time.time()

    # Generate a response
    while True:
        try:
            logger.info("Generating response... at %s", datetime.now())
            completion = ollama.generate(
                model=model_engine, prompt=prompt, options={"temperature": temperature}
            )
            return completion["response"]
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt")
            return ""
        finally:
            logger.info("llama2 request took %s seconds", time.time() - start)
