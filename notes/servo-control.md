# Servo Control — Pan/Tilt Camera Mount

## Hardware

- **Pololu Maestro** USB servo controller (6-channel is plenty)
- **2x MG90S metal gear micro servos** — one for pan (left/right), one for tilt (up/down)
  - 1.8kg/cm torque, 9g weight, 4.8-6V
  - Metal gears are smoother and more durable than plastic SG90s
  - ~$4-5 each, 4-packs under $15 on Amazon
- **Logitech C920** webcam — ~162g (5.7oz), well within MG90S capacity
- **SG90 pan-tilt bracket** — ~$5 plastic bracket designed for micro servos
  - C920 has a clip mount, may need zip-tie or 3D-printed adapter
  - Or start with a Lego mount for prototyping
- **Power** — servos powered from Maestro's separate power rail (5-6V from Jackery), NOT from USB

### Wiring

```
Mac Mini USB → Maestro (data only)
Jackery/battery → Maestro servo power rail (5-6V)
Pan servo → Maestro channel 0
Tilt servo → Maestro channel 1
```

## Software

### Dependencies

```bash
pip install pyserial
```

### Serial Port

The Maestro shows up as `/dev/cu.usbmodem*` on macOS. Find it with:

```bash
ls /dev/cu.usbmodem*
```

### Protocol

The Maestro uses a binary serial protocol. All commands are sent as byte sequences.

#### Set Position

Target is in **quarter-microseconds**:
- 4000 (1000µs) = full one direction
- 6000 (1500µs) = center
- 8000 (2000µs) = full other direction

```python
import serial

port = serial.Serial('/dev/cu.usbmodem00123', 9600)

def set_position(channel, target):
    """Set servo position. Target is in quarter-microseconds."""
    low = target & 0x7F
    high = (target >> 7) & 0x7F
    port.write(bytes([0x84, channel, low, high]))

# Center both servos
set_position(0, 6000)  # pan
set_position(1, 6000)  # tilt
```

#### Set Speed

Limits how fast the servo moves. Useful for smooth camera panning.

```python
def set_speed(channel, speed):
    """Limit servo speed. 0 = unlimited."""
    low = speed & 0x7F
    high = (speed >> 7) & 0x7F
    port.write(bytes([0x87, channel, low, high]))
```

#### Set Acceleration

Limits how fast the servo accelerates/decelerates.

```python
def set_acceleration(channel, accel):
    """Limit servo acceleration. 0 = unlimited."""
    low = accel & 0x7F
    high = (accel >> 7) & 0x7F
    port.write(bytes([0x89, channel, low, high]))
```

#### Get Position

```python
def get_position(channel):
    """Get current servo position in quarter-microseconds."""
    port.write(bytes([0x90, channel]))
    low = ord(port.read())
    high = ord(port.read())
    return low | (high << 8)
```

## Integration Plan

### Channel Mapping

```python
PAN_CHANNEL = 0
TILT_CHANNEL = 1
```

### Iris Functions to Register

| Function | Description |
|---|---|
| `look(pan, tilt)` | Set absolute position (degrees or µs) |
| `look_left` | Pan left |
| `look_right` | Pan right |
| `look_up` | Tilt up |
| `look_down` | Tilt down |
| `look_center` | Center both axes |
| `scan` | Slowly pan across the scene |

### Startup/Shutdown

- Open serial port and center servos on startup (alongside camera init)
- Center servos and close port on shutdown

### Degree Mapping

Convert friendly degrees (0-180) to quarter-microseconds:

```python
def degrees_to_target(degrees):
    """Convert 0-180 degrees to quarter-microsecond target."""
    us = 1000 + (degrees / 180) * 1000  # 1000-2000µs range
    return int(us * 4)  # quarter-microseconds
```

## Lego Technic Integration

### Coupling Servos to Lego

- **Press-fit** — Lego Technic axles (cross-shaped) can press into servo horn holes, hot glue to secure
- **3D-printed adapter** — servo horn mount on one side, Lego axle on the other
- **Lego-compatible servo brackets** — search "SG90 Lego mount" (BrickLink/GeeekPi etc.)

### Gear Options

- **Worm gear** — servo drives a Lego worm gear for slow, precise, self-locking movement (camera stays put when servo is off)
- **Spur gears** — simple gear reduction for more torque
- **Bevel gears** — for right-angle direction changes (useful for tilt axis)

### Pan-Tilt with Lego

- **Pan:** servo on base driving a Lego turntable (lazy susan piece) or worm gear
- **Tilt:** servo driving a Lego Technic gear or linkage arm
- MG90S has plenty of torque for Lego gears + C920 weight

## Force/Load Sensing

Standard hobby servos (MG90S, SG90) have no built-in load feedback. Options:

### Stall Detection (free, no extra hardware)

Use `is_moving()` — if the servo can't reach its target (blocked), it stays in "moving" state indefinitely. Crude but works for detecting collisions.

```python
def is_moving():
    """Check if any servos are still moving to their targets."""
    port.write(bytes([0x93]))
    return ord(port.read()) != 0
```

### Current Sensing (~$5 + I2C adapter)

- INA219 current sensor inline with servo power wire
- Higher current = more load/resistance
- Python library: `adafruit-circuitpython-ina219`
- Needs USB-I2C adapter for Mac (e.g., Adafruit FT232H ~$15)

### Maestro Analog Inputs

- The Maestro 6-channel has analog input on channels not used for servos
- Could read a force-sensitive resistor (FSR) or load cell via ADC
- No extra USB adapter needed

### Smart Servos (expensive)

- Dynamixel servos report position, load, temperature, voltage over serial
- $30-100+ each, overkill for camera mount but standard for real robots

## Notes

- Servos draw significant current under load — don't power from USB
- Set speed/acceleration for smooth movement so the camera doesn't jerk
- Lego mount first, then upgrade to a proper pan-tilt bracket
- The Maestro can be configured via the Pololu Maestro Control Center app (Windows/Linux) but all runtime control is via serial
