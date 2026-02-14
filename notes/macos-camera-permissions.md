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
