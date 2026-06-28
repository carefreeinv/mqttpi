# [pi4-pwm-relay.yaml](pi4-pwm-relay.yaml)

## Purpose / when to use

**Raspberry Pi 4/5** node combining **hardware PWM** on **GPIO12** and **GPIO13** with an auxiliary **relay** on **GPIO17**, all exposed to Home Assistant.

Use for:

- 25 kHz **fan** control (GPIO12) and 1 kHz **dimmer** (GPIO13)
- A separate on/off **relay** for loads that do not need PWM
- Pi-based installations where Pico W PWM is not used

Pico W equivalent for PWM-only: [pwm-bank.md](pwm-bank.md) (software PWM bank GP8–GP15).

## Quick start

```bash
cp examples/pi4-pwm-relay.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

**Wiring:**

- **GPIO12** → fan PWM control wire (often blue on 4-pin fans)
- **GPIO13** → MOSFET dimmer gate for LED strip
- **GPIO17** → relay module IN

Use level-appropriate drivers; Pi GPIO is 3.3 V.

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `pi4` |
| **Profile** | `pwm_only` |
| **PWM** | **`enabled: true`**, pins **[12, 13]** (Pi HW PWM) |
| **1-Wire / I2C / SPI / I2S** | all off |

Unlike Pico W’s eight-line GP8–GP15 bank, Pi 4 exposes **two** common hardware PWM lines in mqttpi defaults.

## GPIO pool / pin map

| BCM GPIO | Alias | Direction | Freq | Initial | HA |
|----------|-------|-----------|------|---------|-----|
| 12 | `fan_pwm` | pwm_output | 25000 Hz | 0% | number, `mdi:fan` |
| 13 | `dimmer_pwm` | pwm_output | 1000 Hz | 0% | number, `mdi:brightness-6` |
| 17 | `relay_aux` | output | — | false (off) | switch |
| 2, 3 | — | I2C reserve | — | — | — |
| 4 | — | 1-Wire reserve | — | — | — |
| 8–11 | — | SPI reserve | — | — | — |
| 14, 15 | — | UART console | — | — | avoid |
| 18–21 | — | I2S reserve | — | — | — |
| Other header pins | — | free in maximum_gpio | — | — | — |

## MQTT & HA entities expected

| Entity | Type | Range | Topics under `mqttpi/pi4-pwm-01` |
|--------|------|-------|----------------------------------|
| `number.fan_pwm` | number | 0–100 % | `gpio/fan_pwm/state`, `gpio/fan_pwm/set` |
| `number.dimmer_pwm` | number | 0–100 % | `gpio/dimmer_pwm/state`, `gpio/dimmer_pwm/set` |
| `switch.relay_aux` | switch | ON/OFF | `gpio/relay_aux/state`, `gpio/relay_aux/set` |

HA device: **Pi 4 PWM Node**. Icons set in config for fan and dimmer entities.

## Design decisions

- **GPIO12 @ 25 kHz** — Matches PC fan PWM expectations (same rationale as GP10/GP11 in [pwm-bank.md](pwm-bank.md)).
- **GPIO13 @ 1 kHz** — Suitable for LED dimming via MOSFET; separate frequency avoids fan whine on wrong pin.
- **Relay on GPIO17** — Keeps PWM pins dedicated; 17 is a safe general-purpose output away from console pins.
- **`profile: pwm_only`** — Marks PWM subsystem active on Pi; aligns with Pico `pwm_only` semantics.
- **Pi PWM pool [12, 13]** — Documented in `pwm.pins` even if you only configure two channels—do not reassign without updating config.

## FAQ

**Q: Why only two PWM pins on Pi vs eight on Pico W?**  
A: mqttpi documents the common **hardware PWM** pair on Pi header GPIO12/13. Additional Pi PWM may be supported later via software layers.

**Q: Can I drop the relay and add a third PWM?**  
A: Not on GPIO12/13 without reusing pins. Use another GPIO as digital on/off ([pi4-maximum-gpio.md](pi4-maximum-gpio.md)) or Pico W GP8–GP15 bank.

**Q: Fan needs minimum duty to spin.**  
A: Set a floor in HA automations (e.g. never below 30 % when “on”)—same as Pico fan channels.

**Q: Does this conflict with BMS serial on GPIO14/15?**  
A: No pin overlap. BMS UART uses 14/15; this example avoids them.

**Q: Servo on Pi?**  
A: Use 50 Hz like [servo-controller.md](servo-controller.md), but prefer Pico W for multi-servo projects unless you add a PCA9685 on I2C.

## Related examples

- [pwm-bank.md](pwm-bank.md) — Pico W four-channel PWM bank
- [pi4-maximum-gpio.md](pi4-maximum-gpio.md) — Pi GPIO without PWM
- [multi-relay.md](multi-relay.md) — Multiple relays, no PWM
- [sites/house.yaml](sites/house.yaml) — Pi 4 dimmer + HVAC outputs

## Implementation status

**Config-only** for Pi GPIO/PWM. Frequencies, duty, and HA **number**/**switch** discovery are defined but not implemented in Python yet. **BMS bridge** (`mqttpi.bms`) is the working HA/MQTT implementation on Pi today.