# [home-assistant.yaml](home-assistant.yaml)

## Purpose / when to use

**Canonical Home Assistant reference** on a Pico W: one **switch**, two **binary_sensor** styles (pull-down motion, inverted pull-up door contact), with full HA device metadata.

Use when you need:

- A copy-paste pattern for HA `device_class`, `icon`, pull, and `invert`
- Documentation of how mqttpi maps GPIO directions to HA entity types
- A test node to verify MQTT discovery in HA before custom wiring

Requires Home Assistant **MQTT integration** with discovery enabled (HA default).

## Quick start

```bash
cp examples/home-assistant.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

After the agent connects, entities should appear under device **HA Reference Node** without manual `configuration.yaml` entries.

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` |
| **Profile** | `maximum_gpio` |
| **HA metadata** | `manufacturer: mqttpi`, `model: picow` |
| **Discovery** | `true`, prefix `homeassistant` |
| **PWM / buses** | all off |

## GPIO pool / pin map

| GPIO | Alias | Direction | Pull | Invert | Debounce | HA |
|------|-------|-----------|------|--------|----------|-----|
| GP0 | `porch_light` | output | — | — | — | switch, `mdi:lightbulb` |
| GP1 | `motion_sensor` | input | down | no | 100 ms | binary_sensor, `motion` |
| GP2 | `door_contact` | input | up | **yes** | 50 ms | binary_sensor, `door` |
| GP3–GP28 | — | free | — | — | — | — |

## MQTT & HA entities expected

| Entity | Type | Topics under `mqttpi/ha-node-01` |
|--------|------|----------------------------------|
| `switch.porch_light` | switch | `gpio/porch_light/state`, `gpio/porch_light/set` |
| `binary_sensor.motion_sensor` | binary_sensor | `gpio/motion_sensor/state` |
| `binary_sensor.door_contact` | binary_sensor | `gpio/door_contact/state` |

Payloads: `ON` / `OFF`, retained, QoS 1.

Discovery publishes `device_class`, `icon`, and device linkage so entities group under **HA Reference Node**.

## Design decisions

- **Three entity types in one file** — Shows switch vs. binary_sensor inference from `direction` only.
- **Motion with `pull: down`** — PIR modules often drive line high on motion; floating low when idle. Adjust if your module is open-collector.
- **Door with `pull: up` + `invert: true`** — Matches NC reed wired to GND when door open—common residential pattern ([garage-door.md](garage-door.md) uses similar for `garage_door` class).
- **`debounce_ms` differs per input** — Motion 100 ms (noisy RF PIR); door 50 ms (mechanical reed).
- **Explicit HA manufacturer/model** — Improves device registry appearance vs. anonymous MQTT nodes.
- **No `mqtt_aliases`** — Aliases shown only when topic names must differ from internal names.

## FAQ

**Q: Entities do not appear in HA.**  
A: Confirm broker host, credentials in `secrets.yaml`, and that HA MQTT integration is connected to the same broker. Check `homeassistant/#` discovery topics with an MQTT client.

**Q: How do I rename entities in HA?**  
A: Change `ha.name` in config and restart/republish discovery. Entity IDs follow `alias` fields (`porch_light`, etc.).

**Q: What if my motion sensor is active-low?**  
A: Try `pull: up` and `invert: true`, or match your module datasheet—duplicate the GP1 block and adjust.

**Q: Can I add a PWM dimmer to the porch light?**  
A: Move lighting control to a `pwm_output` on GP8+ ([pwm-bank.md](pwm-bank.md)) or keep a relay on GP0 for on/off only.

**Q: Is discovery required?**  
A: mqttpi defaults to discovery on. Turning it off means manual MQTT entity configuration in HA—not recommended for new installs.

## Related examples

- [digital-in-out.md](digital-in-out.md) — Minimal switch + button
- [garage-door.md](garage-door.md) — Real-world alias table + garage classes
- [maximum-gpio.md](maximum-gpio.md) — Empty starting point
- [analog-inputs.md](analog-inputs.md) — HA **sensor** (ADC) pattern

## Implementation status

**Config-only.** This file is the reference schema for HA MQTT discovery fields on GPIO entities. Pico W runtime publishing is planned; **BMS bridge** (`mqttpi.bms`) is the implemented HA/MQTT path in this repo today.