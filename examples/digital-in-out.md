# [digital-in-out.yaml](digital-in-out.yaml)

## Purpose / when to use

Minimal **digital I/O** example: one relay output and one momentary button input on a **Pico W**, exposed to Home Assistant as a **switch** and **binary_sensor**.

Use when you need:

- A single controllable load (light, pump, relay module)
- One physical button for automations (toggle, scene trigger, doorbell)
- The smallest useful HA node beyond the empty template

## Quick start

```bash
cp examples/digital-in-out.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

**Wiring:**

- **GP0** → relay module IN (active-high; relay OFF at boot via `initial: false`)
- **GP1** → button leg to **GND** (internal pull-up; pressed = LOW)

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` |
| **Profile** | `maximum_gpio` |
| **1-Wire** | off (GP7 reserved) |
| **I2C** | off (GP0/GP1 free — not used for I2C here) |
| **SPI** | off (GP2–GP5) |
| **I2S** | off (GP16–GP19) |
| **PWM** | off (GP8–GP15) |

All peripheral toggles are **false** so GP0 and GP1 are dedicated to this example.

## GPIO pool / pin map

| GPIO | Alias | Direction | Pull | HA entity |
|------|-------|-----------|------|-----------|
| GP0 | `relay_main` | output | — | switch |
| GP1 | `button_main` | input | up | binary_sensor |
| GP2–GP6 | — | free | — | — |
| GP7 | — | 1-Wire reserve | — | — |
| GP8–GP15 | — | PWM bank reserve | — | — |
| GP16–GP22 | — | free (GP16–19 I2S reserve) | — | — |
| GP26–GP28 | — | ADC-capable, free | — | — |

## MQTT & HA entities expected

| HA entity (typical ID) | Type | Alias | State topic | Command topic |
|------------------------|------|-------|-------------|---------------|
| `switch.relay_main` | switch | `relay_main` | `mqttpi/relay-button-01/gpio/relay_main/state` | `.../set` |
| `binary_sensor.button_main` | binary_sensor | `button_main` | `mqttpi/relay-button-01/gpio/button_main/state` | — |

Discovery: `homeassistant/switch/.../config`, `homeassistant/binary_sensor/.../config`.

HA friendly names from config: **Relay Main**, **Button Main** (`device_class: opening`).

Payloads: `ON` / `OFF` (`mqtt.payload_on` / `payload_off`), `retain: true`, `qos: 1`.

## Design decisions

- **GP0 for relay** — Lowest-numbered free pin; common wiring habit for “channel 1” on relay boards.
- **GP1 for button with pull-up** — One wire to GPIO + one to GND; no external resistor needed.
- **`debounce_ms: 50` on button** — Filters contact bounce for mechanical switches.
- **`device_class: opening`** — Generic “momentary / opening” class; change to `door`, `motion`, etc. to match hardware.
- **`initial: false` on relay** — Safe boot: load off until HA or MQTT explicitly turns on.
- **No `mqtt_aliases`** — Internal `name` and MQTT `alias` match; garage-door pattern uses aliases when names differ.

## FAQ

**Q: My relay is active-low. What do I change?**  
A: Add `invert: true` on the output pin entry, or use a relay module with active-high opto input.

**Q: Can I use GP0/GP1 if I later enable I2C?**  
A: No. I2C defaults to SDA=GP0, SCL=GP1. Enable I2C only on a different pin assignment or use [sensors-i2c-onewire.md](sensors-i2c-onewire.md) as a base.

**Q: The button reads backwards in HA.**  
A: With pull-up, pressed is usually OFF in MQTT unless you set `invert: true`. Match [home-assistant.md](home-assistant.md) patterns for your sensor type.

**Q: How do I add a second relay?**  
A: Copy the GP0 pin block, increment `pin` and `alias`. See [multi-relay.md](multi-relay.md) for a four-channel layout.

**Q: Is TLS supported?**  
A: Set `mqtt.tls: true` and configure broker certificates in secrets; broker host remains in `config.yaml`.

## Related examples

- [maximum-gpio.md](maximum-gpio.md) — Empty template before adding pins
- [multi-relay.md](multi-relay.md) — Four relay outputs on GP0–GP3
- [home-assistant.md](home-assistant.md) — More input patterns (pull-down, invert)
- [garage-door.md](garage-door.md) — Relay + reed + wall button with aliases

## Implementation status

**Config-only.** Relay and button behavior, debounce, and HA MQTT discovery are specified here; the Pico W GPIO agent is not yet implemented in this repository. The **JBD BMS bridge** is the only fully implemented MQTT publisher today.