# [multi-relay.yaml](multi-relay.yaml)

## Purpose / when to use

Four independent **relay outputs** on **GP0–GP3** of a Pico W, each discovered in Home Assistant as its own **switch**.

Use for:

- 4-channel relay modules (mains or low-voltage)
- Irrigation zone valves
- Multi-load power strips with per-channel control
- Any project needing several digital outputs without PWM or sensor buses

## Quick start

```bash
cp examples/multi-relay.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

Wire each relay module input to the matching GPIO (GP0–GP3). Share relay board **VCC** and **GND** with the Pico; do not exceed GPIO current limits—use opto-isolated relay boards for inductive loads.

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` |
| **Profile** | `maximum_gpio` |
| **1-Wire** | off |
| **I2C** | off |
| **SPI** | off |
| **I2S** | off |
| **PWM** | off (`pins: [8…15]` documented, unused) |

Keeping all buses disabled preserves **GP0–GP6** and **GP20–GP22** for digital I/O (four used here).

## GPIO pool / pin map

| GPIO | Alias | Direction | Initial | HA name |
|------|-------|-----------|---------|---------|
| GP0 | `relay_ch1` | output | false | Relay Channel 1 |
| GP1 | `relay_ch2` | output | false | Relay Channel 2 |
| GP2 | `relay_ch3` | output | false | Relay Channel 3 |
| GP3 | `relay_ch4` | output | false | Relay Channel 4 |
| GP4–GP6 | — | free | — | — |
| GP7 | — | 1-Wire reserve | — | — |
| GP8–GP15 | — | PWM bank | — | — |
| GP16–GP22 | — | free / I2S reserve | — | — |
| GP26–GP28 | — | ADC, free | — | — |

## MQTT & HA entities expected

| Entity | Type | Topics under `mqttpi/relay-bank-01` |
|--------|------|-------------------------------------|
| `switch.relay_ch1` | switch | `gpio/relay_ch1/state`, `gpio/relay_ch1/set` |
| `switch.relay_ch2` | switch | `gpio/relay_ch2/state`, `gpio/relay_ch2/set` |
| `switch.relay_ch3` | switch | `gpio/relay_ch3/state`, `gpio/relay_ch3/set` |
| `switch.relay_ch4` | switch | `gpio/relay_ch4/state`, `gpio/relay_ch4/set` |

All four share one HA **device** (**Relay Bank**, `device.id: relay-bank-01`). Discovery prefix: `homeassistant`.

## Design decisions

- **Contiguous GP0–GP3** — Matches typical 4-relay board silkscreen ordering and keeps wiring short on a breadboard.
- **All `initial: false`** — Safe power-on: every channel off until commanded.
- **Separate aliases per channel** — Stable MQTT topic names even if you rename HA display strings in `ha.name`.
- **maximum_gpio profile** — No PWM or buses required; avoids reserving GP8–GP15.
- **Uniform HA naming** — “Relay Channel N” pattern scales if you duplicate pin blocks for GP4–GP6.

## FAQ

**Q: Can I drive more than four relays?**  
A: Yes. Add pin entries on GP4–GP6 (and GP20–GP22) while peripherals stay disabled. Mind total current and use a powered relay board.

**Q: Should channels be interlocked (only one ON)?**  
A: mqttpi does not enforce interlocks in config. Implement exclusivity in Home Assistant automations or application logic.

**Q: Why not use PWM pins for relays?**  
A: GP8–GP15 are the PWM bank; digital relays do not need PWM. Keeping relays on GP0–GP3 leaves the PWM pool free for dimming or fans ([pwm-bank.md](pwm-bank.md)).

**Q: My module needs active-low signals.**  
A: Set `invert: true` on each output pin so HA “ON” still means “energized” from your perspective.

**Q: Can I mix a button input on GP4?**  
A: Yes. Add an `input` pin entry alongside relay outputs in the same `pins[]` array.

## Related examples

- [digital-in-out.md](digital-in-out.md) — Single relay + button
- [pwm-bank.md](pwm-bank.md) — PWM on GP8–GP11 instead of more relays
- [pi4-pwm-relay.md](pi4-pwm-relay.md) — Pi 4 relay + hardware PWM
- [garage-door.md](garage-door.md) — Single relay with safety inputs

## Implementation status

**Config-only.** Four switch entities and MQTT topic layout are defined; Pico W firmware to drive GPIO and publish discovery is planned but not in this repo yet. **BMS bridge** (`mqttpi.bms`) is implemented separately on Raspberry Pi.