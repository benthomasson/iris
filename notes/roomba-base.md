# Roomba Base — Mobile Platform for Iris

## Overview

Use an old Roomba as a mobile base for the Mac Mini + webcam + servos. The Roomba Open Interface (OI) provides serial control of drive motors, sensors, and battery from Python.

## Compatible Models

- **400 series** — original OI, 7-pin mini-DIN connector
- **500 series** — most commonly hacked, well documented
- **600 series** — same OI protocol, easier to find
- **700+ series** — works but less documentation for hacking

## Roomba Open Interface (OI)

### Connection

- Roomba has a serial port on top (mini-DIN connector)
- Use a USB-to-serial adapter (FTDI) or Roomba-specific serial cable
- Baud rate: 115200 (500/600/700 series), 57600 (400 series)
- Shows up as `/dev/cu.usbserial*` on macOS

### Python Control via pyserial

```python
import serial
import struct
import time

port = serial.Serial('/dev/cu.usbserial-00123', 115200)

def start():
    """Wake up and start OI."""
    port.write(bytes([128]))  # Start command
    time.sleep(0.1)
    port.write(bytes([132]))  # Full control mode

def drive(velocity, radius):
    """Drive with velocity (mm/s) and radius (mm).
    velocity: -500 to 500
    radius: -2000 to 2000 (32767 = straight, -1 = spin CW, 1 = spin CCW)
    """
    cmd = struct.pack('>Bhh', 137, velocity, radius)
    port.write(cmd)

def drive_direct(left, right):
    """Drive left and right wheels independently (mm/s).
    -500 to 500 each.
    """
    cmd = struct.pack('>Bhh', 145, right, left)
    port.write(cmd)

def stop():
    drive(0, 0)

# Examples
start()
drive(200, 32767)    # Forward at 200mm/s
drive(200, 1)        # Spin left
drive(-200, 32767)   # Backward
drive_direct(200, -200)  # Spin in place
stop()
```

### Reading Sensors

```python
def read_sensors(packet_id):
    """Request a sensor packet."""
    port.write(bytes([142, packet_id]))
    time.sleep(0.05)
    return port.read(port.in_waiting)

# Useful packet IDs:
# 7  = bump and wheel drops (1 byte)
# 8  = wall sensor (1 byte)
# 9  = cliff left (1 byte)
# 10 = cliff front left (1 byte)
# 11 = cliff front right (1 byte)
# 12 = cliff right (1 byte)
# 21 = charging state (1 byte)
# 22 = battery voltage (2 bytes, unsigned, mV)
# 23 = battery current (2 bytes, signed, mA)
# 25 = battery charge (2 bytes, unsigned, mAh)
# 26 = battery capacity (2 bytes, unsigned, mAh)
```

### Stream Sensors (continuous)

```python
def start_stream(packet_ids):
    """Start streaming sensor data."""
    port.write(bytes([148, len(packet_ids)] + packet_ids))

def stop_stream():
    port.write(bytes([150, 0]))

# Stream bump sensors and battery voltage
start_stream([7, 22])
```

## Power Options

### Option 1: Roomba Battery + Buck Converter
- Roomba battery: 14.4V NiMH (2-3Ah depending on model)
- Buck converter 14.4V → 5V USB-C for Mac Mini (needs 30W adapter but only draws ~4W idle)
- Limited runtime but fully untethered
- Need a 14.4V to USB-C PD converter (or 14.4V to 12V buck + car USB-C adapter)

### Option 2: Overhead Power Cord
- Retractable cord reel mounted on ceiling
- Long flat cable with swivel joint to prevent tangling
- Unlimited runtime, limited range
- Common approach for lab/industrial robots

### Option 3: Tethered Power
- Long extension cord or flat cable trailing behind
- Simple but gets tangled
- OK for indoor demos in a single room

### Option 4: Larger Battery
- Replace Roomba NiMH with a higher capacity LiPo pack
- Or mount a separate battery (Jackery portable, or a RC LiPo with converter)
- Mac Mini at 4W idle: a 100Wh battery = ~25 hours

### Option 5: Roomba Dock Charging
- Keep the Roomba's self-docking behavior
- When battery is low, Iris drives herself back to the dock
- Only works if Mac Mini power is separate (e.g., overhead cord or its own battery)

## Integration Plan

### Iris Functions to Register

| Function | Description |
|---|---|
| `drive_forward(distance)` | Drive forward N mm |
| `drive_backward(distance)` | Drive backward N mm |
| `turn_left(degrees)` | Spin left |
| `turn_right(degrees)` | Spin right |
| `stop` | Stop driving |
| `dock` | Drive to charging dock |
| `get_battery` | Read battery level |
| `get_bumpers` | Read bump sensor state |

### Startup/Shutdown
- Open serial port and send Start + Full Mode on startup
- Send Stop and Safe Mode on shutdown (so Roomba can still protect itself)

### Safety
- Read bump and cliff sensors to avoid collisions/falls
- Set velocity limits (200mm/s max is plenty for indoor use)
- Full Mode disables Roomba's built-in safety — consider Safe Mode instead (Roomba stops on cliff/bump but you still control drive)

## Physical Setup

```
        [Webcam on servo pan/tilt]
                |
           [Mac Mini]
                |
           [Roomba base]
```

- Mac Mini sits on top of Roomba (flat surface, may need a mounting plate)
- Webcam + servo mount on top of Mac Mini
- Cables: USB from Mac to Roomba serial, USB from Mac to Maestro, USB from Mac to webcam
- USB hub recommended

## Notes

- The Roomba OI protocol is well documented: search "iRobot Roomba Open Interface Specification"
- The 500/600 series are the sweet spot for hacking — cheap, available, good docs
- Test serial control before mounting anything — make sure drive commands work reliably
- Roomba wheels have encoders — can do basic odometry for position tracking
- The vacuum motor and brushes can be turned off to save power
