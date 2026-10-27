# [linear-actuator-pwm.yaml](linear-actuator-pwm.yaml)

## Purpose / when to use

A reversible DC linear actuator driven by a **dual-PWM H-bridge** (two PWM inputs, one per direction). This adds speed control to the relay version in [linear-actuator.md](linear-actuator.md). The aliases are the same, so [`linear_actuator_interlock.py`](https://github.com/carefreeinv/mqttpi/blob/main/examples/linear_actuator_interlock.py) applies the same software interlocks:

- `actuator_extend` and `actuator_retract` are mutually exclusive. One cannot go above 0 % while the other is above 0 %. Set the active one to 0 first.
- Extending is blocked while `limit_extended` is ON, and retracting is blocked while `limit_retracted` is ON.

## Quick start

```bash
cp examples/linear-actuator-pwm.yaml config.yaml    # edit device.id, mqtt.host
python3 examples/linear_actuator_interlock.py -c config.yaml --mock-gpio -v   # no hardware
python3 examples/linear_actuator_interlock.py -c config.yaml -v               # on the Pi
```

Drive it over MQTT (or from the Home Assistant number sliders):

```bash
mosquitto_pub -h BROKER -t mqttpi/actuator-01/gpio/actuator_enable/set -m ON
mosquitto_pub -h BROKER -t mqttpi/actuator-01/gpio/actuator_extend/set -m 60    # extend at 60 %
mosquitto_pub -h BROKER -t mqttpi/actuator-01/gpio/actuator_extend/set -m 0     # stop
mosquitto_pub -h BROKER -t mqttpi/actuator-01/gpio/actuator_retract/set -m 100  # retract full speed
```

`ON` and `OFF` are accepted too, as `ha.max` and 0 %.

## Pin map (BCM numbering)

| GPIO | Alias | Wire to |
|------|-------|---------|
| 12 | `actuator_extend` | H-bridge PWM input A (e.g. RPWM) |
| 13 | `actuator_retract` | H-bridge PWM input B (e.g. LPWM) |
| 5 | `actuator_enable` | Both enable inputs (R_EN + L_EN), or tie them to 3.3 V |
| 22, 23 | `limit_extended`, `limit_retracted` | End-stop switches to GND |
| GND | — | Driver logic GND (common ground with the Pi) |

## Notes

- **Software PWM** (the default) at 1 kHz is fine for DC motor speed, though the motor may whine audibly. For a quieter 20 kHz+, use `pwm_mode: hardware` on GPIO 12/13 with `dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4` in `/boot/firmware/config.txt`; see [daemon.md](../daemon.md#pwm-outputs).
- **The interlock only gates commands.** It does not stop a moving actuator when an end stop closes. Most actuators have built-in limit switches; rely on those, or wire the end stops into the driver's enable line.
- On daemon shutdown, every PWM output is set to 0 %.
