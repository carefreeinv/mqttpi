# [pi4-maximum-gpio.yaml](pi4-maximum-gpio.yaml)

## Purpose / when to use

**Raspberry Pi 4/5** equivalent of the empty GPIO template: **maximum_gpio** profile with all peripheral buses off, plus one **relay** and one **button** example on BCM **GPIO17** and **GPIO27**.

Use when you need:

- Pi-hosted mqttpi (alongside or instead of Pico W nodes)
- Wired Ethernet and more CPU for bridges (BMS, CAN, etc.)
- ~**26 free GPIO** lines on the 40-pin header (BCM numbering)

**GPIO 14/15** are reserved for the serial console and are **not** used here.

## Quick start

```bash
cp examples/pi4-maximum-gpio.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

Run on the Pi after installing mqttpi; GPIO agent TBD—config defines the contract.

**Wiring:**

- **GPIO17** → relay module input
- **GPIO27** → button to GND (pull-up)

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `pi4` (Pi 4/5 family) |
| **Profile** | `maximum_gpio` |
| **1-Wire** | off (default pin GPIO4) |
| **I2C** | off (controller 1, SDA GPIO2, SCL GPIO3) |
| **SPI** | off (GPIO8–11) |
| **I2S** | off (GPIO18–21) |
| **PWM** | off (hardware PWM pool **GPIO12, GPIO13**) |

Pi bus defaults differ from Pico W—always read `buses` and `pwm` sections when copying between boards.

## GPIO pool / pin map

| BCM GPIO | Alias | Direction | Notes |
|----------|-------|-----------|-------|
| 17 | `relay_main` | output | HA switch |
| 27 | `button_main` | input, pull-up | HA binary_sensor |
| 2, 3 | — | I2C reserve | free while I2C off |
| 4 | — | 1-Wire reserve | free while off |
| 8–11 | — | SPI reserve | free while off |
| 12, 13 | — | HW PWM reserve | free while `pwm.enabled: false` |
| 14, 15 | — | **UART console** | avoid |
| 18–21 | — | I2S reserve | free while off |
| Others | — | ~26 GPIO pool | per README |

## MQTT & HA entities expected

| Entity | Type | Topics under `mqttpi/pi4-node-01` |
|--------|------|-----------------------------------|
| `switch.relay_main` | switch | `gpio/relay_main/state`, `gpio/relay_main/set` |
| `binary_sensor.button_main` | binary_sensor | `gpio/button_main/state` |

HA device: **Pi 4 Node**. Discovery on, payloads `ON`/`OFF`, retained.

## Design decisions

- **`board: pi4`** — Selects Pi header pin map and PWM capabilities vs. `picow`.
- **GPIO17 / GPIO27** — Common, well-separated pins on the 40-pin header; avoids console (14/15) and default I2C (2/3) if you enable I2C later.
- **PWM pins 12/13 documented but disabled** — Pi hardware PWM pool; enable in [pi4-pwm-relay.md](pi4-pwm-relay.md).
- **Same HA patterns as Pico** — `device_class: opening` on button matches [digital-in-out.md](digital-in-out.md).
- **maximum_gpio with buses off** — Maximizes free pins before enabling 1-Wire/I2C/SPI/I2S like [sites/house.yaml](sites/house.yaml).

## FAQ

**Q: Pi 5 vs Pi 4—same config?**  
A: mqttpi uses `board: pi4` for the family; verify pin capabilities on Pi 5 if using specialized peripherals.

**Q: Can this Pi run the BMS bridge too?**  
A: Yes. See [jbd-bms.yaml](jbd-bms.yaml)—UART on `/dev/serial0` (GPIO14/15)—separate from this GPIO example.

**Q: Why not use GPIO14/15 for the relay?**  
A: They are typically mapped to the serial console; using them breaks login console and serial gadgets.

**Q: How do I enable I2C?**  
A: Set `buses.i2c.enabled: true` and avoid assigning GPIO2/3 in `pins[]`. Use `profile: sensors` for sensor-heavy setups.

**Q: Is there a Pico equivalent?**  
A: [digital-in-out.md](digital-in-out.md) on GP0/GP1—same logical layout, different pin numbers.

## Related examples

- [pi4-pwm-relay.md](pi4-pwm-relay.md) — Hardware PWM on GPIO12/13 + relay
- [digital-in-out.md](digital-in-out.md) — Pico W relay + button
- [maximum-gpio.md](maximum-gpio.md) — Pico W empty template
- [jbd-bms.yaml](jbd-bms.yaml) — Implemented Pi UART bridge

## Implementation status

**Config-only** for GPIO relay/button. The **JBD BMS bridge** (`python3 -m mqttpi.bms.bridge`) is **implemented** on Raspberry Pi and publishes HA MQTT discovery. GPIO switching for this config is not yet implemented in-tree.