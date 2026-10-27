# [linear-actuator.yaml](linear-actuator.yaml)

## Purpose / when to use

A reversible DC **linear actuator** (or any reversible motor) driven by **two relays** — one per direction — on a Raspberry Pi, with optional **end-stop inputs**. The companion script [`linear_actuator_interlock.py`](https://github.com/carefreeinv/mqttpi/blob/main/examples/linear_actuator_interlock.py) runs the stock daemon with [command filters](../daemon.md#command-filters) so:

- `actuator_extend` and `actuator_retract` are never ON together (a second direction command is rejected until the first is switched OFF);
- extending is refused while `limit_extended` is active, retracting while `limit_retracted` is active.

For speed control with a dual-PWM H-bridge, see [linear-actuator-pwm.md](linear-actuator-pwm.md).

## Quick start

```bash
cp examples/linear-actuator.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml

# Try it without hardware first
python3 examples/linear_actuator_interlock.py -c config.yaml --mock-gpio -v

# On the Pi
python3 examples/linear_actuator_interlock.py -c config.yaml -v
```

Plain `python3 -m mqttpi` also works with this config, but **without** the interlocks.

## Pin map (BCM numbering)

| GPIO | Alias | Direction | Notes |
|------|-------|-----------|-------|
| 17 | `actuator_extend` | output | Relay → actuator + direction |
| 27 | `actuator_retract` | output | Relay → actuator − direction |
| 22 | `limit_extended` | input, pull-up, inverted | Optional end stop (switch to GND) |
| 23 | `limit_retracted` | input, pull-up, inverted | Optional end stop (switch to GND) |

Delete the two limit pins if your actuator has built-in limit switches; the script only adds end-stop interlocks for pins that exist.

## MQTT & HA entities

| Entity | Type | Topics under `mqttpi/actuator-01` |
|--------|------|-----------------------------------|
| Actuator Extend | switch | `gpio/actuator_extend/state`, `gpio/actuator_extend/set` |
| Actuator Retract | switch | `gpio/actuator_retract/state`, `gpio/actuator_retract/set` |
| Limit Extended | binary_sensor | `gpio/limit_extended/state` |
| Limit Retracted | binary_sensor | `gpio/limit_retracted/state` |

Manual test from any MQTT client:

```bash
mosquitto_pub -h <broker> -t mqttpi/actuator-01/gpio/actuator_extend/set -m ON
mosquitto_pub -h <broker> -t mqttpi/actuator-01/gpio/actuator_retract/set -m ON   # rejected, state stays OFF
mosquitto_pub -h <broker> -t mqttpi/actuator-01/gpio/actuator_extend/set -m OFF
```

## Wiring notes

- Most relay modules are **active-low**: set `invert: true` on both outputs so HA "ON" means "relay energized". Check before connecting the actuator — with the wrong setting the relay closes at boot.
- Use a DPDT / H-bridge arrangement so the supply cannot short even if both relays close; the software interlock is a second layer, not the only one.
- Size relays for the actuator's stall current, and fuse the motor supply.

## FAQ

**Q: Why is my retract command ignored?**  
A: Extend is still ON (or the retracted limit is active). The log shows `Command actuator_retract → ON rejected: …`. Switch extend OFF first.

**Q: Can I auto-stop at a timeout?**  
A: Not in this example; add an HA automation or your own filter/timer in the script.
