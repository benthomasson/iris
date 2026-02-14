
import subprocess


def say(text):
    if text:
        print(text)
        try:
            subprocess.run(["say", "-r", "180", "--", text], start_new_session=True)
        except KeyboardInterrupt:
            pass
