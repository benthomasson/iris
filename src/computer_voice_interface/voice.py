
import subprocess


def say(text):
    if text:
        print(text)
        try:
            subprocess.run(["say", "--", text])
        except KeyboardInterrupt:
            pass
