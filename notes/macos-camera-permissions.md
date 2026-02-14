# macOS Camera Permissions with tmux

## Problem

OpenCV fails to access the webcam when running inside tmux:

```
OpenCV: not authorized to capture video (status 0), requesting...
OpenCV: camera failed to properly initialize!
```

## Cause

tmux runs as a separate server process. If the tmux server was started outside of an authorized terminal (e.g. at login, via launchd, or from a session before camera permissions were granted), it won't inherit camera access — even if Terminal.app itself has Camera permissions enabled.

## Fix

1. Grant Camera permission to Terminal.app: **System Settings > Privacy & Security > Camera > Terminal** (toggle ON)
2. Kill the tmux server: `tmux kill-server`
3. Relaunch Terminal.app
4. Start tmux fresh from within Terminal — it inherits the camera permission

## Notes

- Just closing and reopening a tmux window is not enough — the tmux *server* must be restarted
- Same issue applies to other macOS permissions (microphone, screen recording, etc.)
- Other terminal apps (iTerm2, Alacritty, etc.) need the same treatment if used instead of Terminal.app
- tmux may also lose inherited permissions over time (needs further investigation)
- **USB disconnect/reconnect revokes permissions**: If the camera or mic is unplugged (e.g. moving the Mac), macOS revokes access. Reconnecting the hardware does NOT restore permissions to the running tmux server — the stale revocation persists. Symptom: mic calibration times out at launch, `r.listen()` hangs. Fix: `tmux kill-server` and relaunch from authorized Terminal.app.

## Screen Lock Revokes Access

macOS revokes camera and microphone access when the screen locks. The revocation is not instantaneous — there's a brief delay after the lock event before hardware is cut off. This can cause errors mid-capture if the timing is unlucky.

### Workarounds

- **Prevent display sleep**: `caffeinate -d` (built into macOS since 10.8, only lasts while running)
- **Disable sleep entirely**: `sudo pmset -a disablesleep 1` (persists until reversed with `sudo pmset -a disablesleep 0`)
- **System Settings**: Lock Screen > adjust "Turn display off" and "Require password" timers
- **Error handling**: Consider graceful handling around `capture_image` calls in case the camera disappears mid-session
