# [pwm-bank.yaml](pwm-bank.yaml)

## Purpose / when to use

Four **PWM output channels** on the Pico W **PWM bank (GP8–GP11)**, exposed in Home Assistant as **number** entities (0–100 % duty).

Use for:

- LED dimming (GP8/GP9 at 1 kHz)
- 4-wire PC fans (GP10/GP11 at 25 kHz)
- Generic duty-cycle control—not hobby servos (use [servo-controller.md](servo-controller.md) at 50 Hz)

## Quick start

```bash
cp examples/pwm-bank.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

Connect PWM loads to **GP8–GP11** through appropriate drivers (MOSFET, fan tach ignored here). Pico GPIO is 3.3 V logic; level-shift or driver boards for 5 V or mains.

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` |
| **Profile** | `pwm_only` |
| **PWM** | **`enabled: true`** — pins GP8–GP15 in pool; **GP8–GP11 used** |
| **1-Wire** | off |
| **I2C** | off |
| **SPI** | off |
| **I2S** | off |

`pwm_only` signals that the PWM bank is active; GP12–GP15 remain available for additional `pwm_output` pins if you extend this config.

## GPIO pool / pin map

| GPIO | Alias | Direction | Freq (Hz) | Initial duty | HA name |
|------|-------|-----------|-----------|--------------|---------|
| GP8 | `pwm_ch1` | pwm_output | 1000 | 0% | PWM Channel 1 |
| GP9 | `pwm_ch2` | pwm_output | 1000 | 0% | PWM Channel 2 |
| GP10 | `pwm_ch3` | pwm_output | 25000 | 0% | PWM Channel 3 |
| GP11 | `pwm_ch4` | pwm_output | 25000 | 0% | PWM Channel 4 |
| GP12–GP15 | — | PWM pool spare | — | — | — |
| GP0–GP7 | — | free (bus reserves) | — | — | — |
| GP16–GP22 | — | free / I2S reserve | — | — | — |
| GP26–GP28 | — | ADC only | — | — | — |

## MQTT & HA entities expected

| Entity | Type | Range | Unit | Topics |
|--------|------|-------|------|--------|
| `number.pwm_ch1` | number | 0–100, step 1 | % | `mqttpi/pwm-bank-01/gpio/pwm_ch1/state\|set` |
| `number.pwm_ch2` | number | 0–100, step 1 | % | `.../pwm_ch2/...` |
| `number.pwm_ch3` | number | 0–100, step 1 | % | `.../pwm_ch3/...` |
| `number.pwm_ch4` | number | 0–100, step 1 | % | `.../pwm_ch4/...` |

HA discovery publishes `min`, `max`, `step`, and `unit_of_measurement` from each pin’s `ha` block.

## Design decisions

- **GP8–GP15 as canonical Pico W PWM bank** — mqttpi convention; `pwm.pins` lists the full bank even when only four channels are configured.
- **`profile: pwm_only`** — Documents that PWM hardware is claimed; digital relays should use GP0–GP7 instead ([multi-relay.md](multi-relay.md)).
- **1 kHz vs 25 kHz split** — Ch1–2 suited to visible LED dimming; Ch3–4 at 25 kHz avoids audible whine on 4-pin fans.
- **`initial_duty: 0`** — Fans off and lights dark at boot until HA sets a value.
- **Number entities, not switches** — Brightness/speed need granular control; servos need 50 Hz ([servo-controller.md](servo-controller.md)).

## FAQ

**Q: Why are channels 3 and 4 at 25 kHz?**  
A: Standard PC fans expect ~25 kHz PWM on the control wire. Channels 1–2 use 1 kHz, typical for LED dimming experiments.

**Q: Can I use all eight PWM pins (GP8–GP15)?**  
A: Yes. Duplicate a pin block, assign GP12–GP15, and add matching `ha` names.

**Q: Will this drive a servo?**  
A: Not ideally. Servos want **50 Hz** with duty mapped to angle—use [servo-controller.md](servo-controller.md).

**Q: HA slider jumps or fan never starts.**  
A: Many fans need a minimum duty (~20–30 %). Add an HA automation template or calibrate `min` in automations.

**Q: Does enabling I2C conflict with PWM?**  
A: I2C uses GP0/GP1; PWM uses GP8–GP15. No overlap. SPI and I2S do conflict with some GPIO if enabled ([full-peripherals.md](full-peripherals.md)).

## Related examples

- [servo-controller.md](servo-controller.md) — 50 Hz hobby servos on GP8–GP11
- [pi4-pwm-relay.md](pi4-pwm-relay.md) — Pi 4 hardware PWM on GPIO 12/13
- [full-peripherals.md](full-peripherals.md) — PWM plus all buses enabled
- [maximum-gpio.md](maximum-gpio.md) — PWM disabled baseline

## Implementation status

**Config-only.** PWM frequencies, duty scaling, and HA **number** discovery are specified; the Pico W PWM runtime is not yet in this repository. Only the **BMS MQTT bridge** is fully implemented today.