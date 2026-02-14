
import subprocess

VOICE = "Moira (Enhanced)"
RATE = 180
PITCH = 50
QUIET = False


def say(text):
    if text:
        print(text)
        if QUIET:
            return
        try:
            subprocess.run(
                ["say", "-v", VOICE, "-r", str(RATE), "--", f"[[pbas {PITCH}]] " + text],
                start_new_session=True,
            )
        except KeyboardInterrupt:
            pass
