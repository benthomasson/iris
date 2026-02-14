
import subprocess

VOICE = "Moira"
RATE = 180
PITCH = 50


def say(text):
    if text:
        print(text)
        try:
            subprocess.run(
                ["say", "-v", VOICE, "-r", str(RATE), "--", f"[[pbas {PITCH}]] " + text],
                start_new_session=True,
            )
        except KeyboardInterrupt:
            pass
