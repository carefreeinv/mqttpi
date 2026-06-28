# [garage-door.yaml](garage-door.yaml)

## Purpose / when to use

**Garage door opener** integration: momentary **relay pulse** to trigger the opener, **reed switch** for closed position, and **wall button** input—all on a Pico W with Home Assistant discovery and **MQTT alias** remapping.

Use when you need:

- HA control of a dry-contact garage opener (not direct motor drive)
- Closed/open inference from a reed on the door track
- Wall button monitoring for automations (arrival scenes, alerts)

## Quick start

```bash
cp examples/garage-door.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

**Typical wiring:**

- **GP0** → opener dry-contact / relay module (momentary pulse via HA automation)
- **GP1** → reed switch (door closed = contact closed); `invert: true`, pull-up
- **GP2** → wall button to GND, pull-up

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` |
| **Profile** | `maximum_gpio` |
| **HA device** | **Garage Door** (`manufacturer: mqttpi`, `model: picow`) |
| **PWM / buses** | all off |
| **base_topic** | `home/garage` (site-style topic; not `mqttpi/…`) |

## GPIO pool / pin map

| GPIO | Internal name | MQTT alias | Direction | HA entity |
|------|---------------|------------|-----------|-----------|
| GP0 | `opener_relay` | `door_trigger` | output | switch |
| GP1 | `reed_closed` | `door_closed` | input (invert, pull-up) | binary_sensor |
| GP2 | `wall_button` | `door_button` | input (pull-up) | binary_sensor |
| GP3–GP7 | — | free / 1-Wire reserve | — | — |
| GP8–GP15 | — | PWM reserve | — | — |
| GP16–GP28 | — | free / ADC | — | — |

## MQTT & HA entities expected

**Alias table** (`mqtt_aliases`):

| Internal name | MQTT / HA alias |
|---------------|-----------------|
| `opener_relay` | `door_trigger` |
| `reed_closed` | `door_closed` |
| `wall_button` | `door_button` |

| Entity | Type | Topics under `home/garage` |
|--------|------|----------------------------|
| `switch.door_trigger` | switch | `gpio/door_trigger/state`, `gpio/door_trigger/set` |
| `binary_sensor.door_closed` | binary_sensor | `gpio/door_closed/state` |
| `binary_sensor.door_button` | binary_sensor | `gpio/door_button/state` |

HA names: **Door Trigger** (`mdi:garage`), **Door Closed** (`device_class: garage_door`), **Wall Button** (`device_class: opening`).

Use a Home Assistant **cover** or **template** automation for full open/close semantics—this config exposes the underlying hardware primitives.

## Design decisions

- **`mqtt_aliases` separate from `name`** — Firmware/logical names (`opener_relay`) can differ from stable MQTT topic slugs (`door_trigger`) expected by existing automations.
- **Reed on GP1 with `invert: true`** — Pull-up + NC/NO reed wiring varies; invert aligns “closed” with HA `garage_door` semantics.
- **`debounce_ms: 50` on reed, `30` on button** — Reed is mechanical; wall buttons are often snappier.
- **`base_topic: home/garage`** — Matches residential site layouts ([sites/house.yaml](sites/house.yaml)); easier broker ACL rules than generic `mqttpi/`.
- **Switch, not cover, on relay** — Opener expects a short pulse; HA automations should pulse `door_trigger` ON briefly then OFF—safer than a latching cover command.

## FAQ

**Q: How do I pulse the opener from HA?**  
A: Automation: turn `switch.door_trigger` on for ~0.5 s, then off. Never leave the relay latched ON unless your opener documentation requires it.

**Q: Why no `cover.garage_door` entity?**  
A: mqttpi exposes GPIO-level entities. Combine reed + trigger in HA for a `template` cover if desired.

**Q: Reed reads open when door is closed.**  
A: Toggle `invert: true` or swap reed mounting (NO vs NC).

**Q: Can I skip the wall button input?**  
A: Remove the GP2 pin block and `wall_button` alias entry; opener and reed still work.

**Q: Is this safe for my opener’s warranty?**  
A: Use only the manufacturer-approved dry-contact terminals. This config drives an isolated relay, not mains voltage on GPIO.

## Related examples

- [digital-in-out.md](digital-in-out.md) — Simpler relay + button without aliases
- [home-assistant.md](home-assistant.md) — Inverted contact pattern (`door_contact`)
- [sites/house.yaml](sites/house.yaml) — Whole-house contacts including garage
- [maximum-gpio.md](maximum-gpio.md) — Strip down to add your own pins

## Implementation status

**Config-only.** Garage door pin roles, alias table, and HA discovery metadata are defined; Pico W GPIO agent not yet in this repository. **BMS bridge** on Pi is separately implemented.