#!/usr/bin/env python3

"""
Usage:
    summarize [options] <text-file>

Options:
    -h, --help         Show this page
    --debug            Show debug logging
    --verbose          Show verbose logging
    --chunk-size=<c>   Chunk size [default: 3500]
    --tokens=<t>       Max tokens [default: 256]
"""
from docopt import docopt
import logging
import os
import sys
from . import llm
import spacy

nlp = spacy.load("en_core_web_sm")

logger = logging.getLogger("summarize")


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parsed_args = docopt(__doc__, args)
    if parsed_args["--debug"]:
        logging.basicConfig(level=logging.DEBUG)
    elif parsed_args["--verbose"]:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    with open(parsed_args["<text-file>"]) as f:
        text = f.read()

    chunk_size = int(parsed_args["--chunk-size"])
    max_tokens = int(parsed_args["--tokens"])

    doc = nlp(text)
    # Summarize the text
    # for each chunk, summarize
    for i, chunk in enumerate(chunks(doc, chunk_size)):
        print(i)
        prompt = (
            "Summarize the text starting with BEGIN and ending with END: \nBEGIN\n"
            + str(chunk)
            + "\nEND"
        )
        print(llm.generate_response(prompt, max_tokens=max_tokens))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
