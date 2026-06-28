# [full-peripherals.yaml](full-peripherals.yaml)

## Purpose / when to use

**Stress-test / coprocessor** layout: every Pico W peripheral bus **enabled** (1-Wire, I2C, SPI, I2S) plus the **PWM bank (GP8–GP15)**, with a single **status LED** on the last convenient free GPIO (**GP6**).

Use when you need:

- Maximum peripheral footprint on one Pico W (sensor fusion + audio + SPI display + PWM)
- A reference for **pin reservations** when everything is turned on
- An I/O coprocessor talking MQTT while a Pi handles heavy logic

Not a starting template for beginners—use [maximum-gpio.md](maximum-gpio.md) unless you truly need all buses.

## Quick start

```bash
cp examples/full-peripherals.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

Only **GP6** is assigned in `pins[]`; wire a status LED (with resistor) or leave as a heartbeat output.

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` |
| **Profile** | `full_peripherals` |
| **1-Wire** | **on**, GP7 |
| **I2C** | **on**, SDA GP0, SCL GP1 |
| **SPI** | **on**, SCK GP2, MOSI GP3, MISO GP4, CS GP5 |
| **I2S** | **on**, BCLK GP16, LRCK GP17, DIN GP18, DOUT GP19 |
| **PWM** | **on**, GP8–GP15 |

## GPIO pool / pin map

| GPIO | Reservation | Available for `pins[]`? |
|------|-------------|-------------------------|
| GP0 | I2C SDA | **No** |
| GP1 | I2C SCL | **No** |
| GP2 | SPI SCK | **No** |
| GP3 | SPI MOSI | **No** |
| GP4 | SPI MISO | **No** |
| GP5 | SPI CS | **No** |
| GP6 | `status_led` (output) | **Yes — used** |
| GP7 | 1-Wire | **No** |
| GP8–GP15 | PWM bank | **No** (unless declared `pwm_output`) |
| GP16 | I2S BCLK | **No** |
| GP17 | I2S LRCK | **No** |
| GP18 | I2S DIN | **No** |
| GP19 | I2S DOUT | **No** |
| GP20–GP22 | — | **Yes — free** |
| GP26–GP28 | ADC | **Yes** (analog_input only) |

With all peripherals on, **GP6**, **GP20–GP22**, and **GP26–GP28** are the practical expansion pool (~7 lines).

## MQTT & HA entities expected

| Entity | Type | Topics under `mqttpi/coprocessor-01` |
|--------|------|--------------------------------------|
| `switch.status_led` | switch | `gpio/status_led/state`, `gpio/status_led/set` |

HA: **Status LED**, icon `mdi:led-outline`.

Bus peripherals (I2S SFX, SPI devices, 1-Wire temps) will add more entities when their drivers publish discovery—see [sites/house.yaml](sites/house.yaml) for Pi 4 I2S SFX pattern.

## Design decisions

- **`full_peripherals` profile** — Documents worst-case pin locking for validators and docs.
- **Status LED on GP6** — Last “low” GPIO not consumed by SPI/1-Wire; visible heartbeat without touching PWM or I2S clocks.
- **All bus defaults match mqttpi Pico W convention** — Same pin numbers whether `enabled: true` or false in other examples; only toggles differ.
- **PWM bank fully enabled** — Reserves GP8–GP15 for dimmers, fans, or servos without reconfiguring `pwm.pins`.
- **Minimal `pins[]`** — Encourages adding only what fits the remaining pool; avoids accidental SPI/I2C pin reuse.

## FAQ

**Q: Why only one switch in HA?**  
A: This example proves MQTT/HA still works when every bus is claimed. Add inputs on GP20–GP22 or ADC pins as needed.

**Q: Can I play audio and use SPI display together?**  
A: Config allows both; bandwidth and CPU on the future agent will be the limit—not GPIO overlap.

**Q: I do not need I2S—can I free GP16–GP19?**  
A: Set `buses.i2s.enabled: false` and switch to `sensors` or `maximum_gpio` profile semantics.

**Q: How is this different from [sensors-i2c-onewire.md](sensors-i2c-onewire.md)?**  
A: Sensors enables I2C + 1-Wire only. Full peripherals adds SPI, I2S, and PWM—far fewer free GPIO.

**Q: Will PWM pins also appear as numbers without `pins[]` entries?**  
A: No. Declare each `pwm_output` in `pins[]` ([pwm-bank.md](pwm-bank.md)) for HA **number** entities.

## Related examples

- [maximum-gpio.md](maximum-gpio.md) — Opposite: nothing enabled
- [sensors-i2c-onewire.md](sensors-i2c-onewire.md) — I2C + 1-Wire only
- [pwm-bank.md](pwm-bank.md) — PWM channels defined in `pins[]`
- [sites/house.yaml](sites/house.yaml) — Pi 4 with I2S SFX tracks

## Implementation status

**Config-only.** Peripheral enable flags and the lone status LED entity are specified; multi-bus firmware for Pico W is not in this repository. **BMS bridge** on Pi is the implemented MQTT component.