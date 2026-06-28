# Mobile robot (differential drive)

**Config:** [`robot.yaml`](robot.yaml)

## Purpose

Template for a **small MQTT-controlled rover** on Pico W: PWM motor speeds, direction GPIO, bumpers, e-stop, status LED, optional **VL53L0X** front rangefinder on I2C.

## Quick start

```bash
cp examples/robot.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

Use an L298N, TB6612, or similar **motor driver** — never wire motors directly to Pico pins.

## Hardware

| Signal | Pin | Role |
|--------|-----|------|
| I2C SDA/SCL | GP0/GP1 | VL53L0X @ 0x29 (optional) |
| Left PWM | GP8 | Motor speed |
| Right PWM | GP9 | Motor speed |
| Left DIR | GP2 | H-bridge direction |
| Right DIR | GP3 | H-bridge direction |
| Front bumper | GP4 | Safety input |
| Rear bumper | GP5 | Safety input |
| E-stop | GP6 | Active-low estop |
| Status LED | GP10 | Heartbeat / fault |
| Driver enable | GP11 | Motor driver ENABLE |

## MQTT / HA

| Entity | Type |
|--------|------|
| `number.motor_left_pwm` | 0–100 % |
| `number.motor_right_pwm` | 0–100 % |
| `switch.motor_left_dir` | Forward |
| `switch.motor_right_dir` | Forward |
| `binary_sensor.bumper_front` | Safety |
| `binary_sensor.estop` | Safety |
| `sensor.front_range_mm` | Distance (if sensor populated) |

## Design decisions

| Decision | Rationale |
|----------|-----------|
| 20 kHz PWM | Typical for DC motor drivers; above audible range |
| `enable_drivers` output | Hardware interlock — motors off until HA enables |
| I2C rangefinder optional | `sensors.range.enabled` can be set false to free conceptually |
| E-stop invert | Matches normally-closed estop chain |

## FAQ

**Q: Can HA joystick / gamepad drive this?**  
A: Yes — automations map joystick MQTT payloads to `motor_*_pwm` number entities (once daemon runs).

**Q: Why not use all 8 PWM pins?**  
A: Differential drive needs only 2; remaining PWM bank pins stay available for servos/gripper.

**Q: Is ROS required?**  
A: No — plain MQTT + HA; ROS bridge could subscribe later.

**Q: Implementation status?**  
A: **Config only** — GPIO/PWM/I2C runtime not merged into unified daemon yet.

## Related

- [`servo-controller.md`](servo-controller.md) — arm/gripper servos
- [`pwm-bank.md`](pwm-bank.md) — PWM bank details
- [`relay-bank-32.md`](relay-bank-32.md) — high channel count outputs

## Safety

Always wire **e-stop in hardware** to cut motor power independently of firmware. MQTT control is not safety-rated.