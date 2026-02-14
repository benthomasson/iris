
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
            cmd = ["say"]
            if VOICE and VOICE.lower() != "none":
                cmd += ["-v", VOICE]
            cmd += ["-r", str(RATE), "--", f"[[pbas {PITCH}]] " + text]
            subprocess.run(cmd, start_new_session=True)
        except KeyboardInterrupt:
            pass
