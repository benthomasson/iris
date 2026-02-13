
import subprocess


def say(text):
    if text:
        print(text)
        try:
            subprocess.run(["say", "-r", "235", "--", text])
        except KeyboardInterrupt:
            pass
