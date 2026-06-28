# [sensors-i2c-onewire.yaml](sensors-i2c-onewire.yaml)

## Purpose / when to use

**Sensor node** profile with **I2C** and **1-Wire** buses enabled on a Pico W, plus two **GPIO binary_sensor** inputs for enclosure and leak detection.

Use when you plan to attach:

- **I2C:** BME280, MPU6050, SSD1306, etc. (SDA GP0, SCL GP1)
- **1-Wire:** DS18B20 temperature strings (GP7)
- Immediate HA visibility for **contact** and **leak** inputs while bus sensor discovery matures

Bus-attached sensors (BME280, DS18B20) will get full HA MQTT discovery in a **later implementation phase**; this example documents bus toggles and working GPIO entities today.

## Quick start

```bash
cp examples/sensors-i2c-onewire.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

**Wiring:**

- **I2C:** SDA → GP0, SCL → GP1, 3.3 V + GND to sensor
- **1-Wire:** GP7 → DS18B20 data (4.7 kΩ pull-up to 3.3 V typical)
- **GP6:** enclosure lid switch to GND, pull-up
- **GP20:** leak sensor (often active-high wet), pull-down

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` |
| **Profile** | `sensors` |
| **1-Wire** | **`enabled: true`**, pin **GP7** |
| **I2C** | **`enabled: true`**, controller 0, **SDA GP0**, **SCL GP1** |
| **SPI** | off (would use GP2–GP5) |
| **I2S** | off (GP16–GP19) |
| **PWM** | off (GP8–GP15) |

Enabling I2C **reserves GP0/GP1**; do not assign those as digital I/O in `pins[]`.

## GPIO pool / pin map

| GPIO | Role | Used by |
|------|------|---------|
| GP0 | I2C SDA | bus (reserved) |
| GP1 | I2C SCL | bus (reserved) |
| GP2–GP5 | SPI reserve | free while SPI off |
| GP6 | `enclosure_lid` | input, pull-up |
| GP7 | 1-Wire data | bus (reserved) |
| GP8–GP15 | PWM bank | free while PWM off |
| GP16–GP19 | I2S reserve | free while I2S off |
| GP20 | `leak_detector` | input, pull-down |
| GP21–GP22 | — | free |
| GP26–GP28 | ADC | free |

## MQTT & HA entities expected

**Today (GPIO inputs):**

| Entity | Type | Class | Topic under `mqttpi/sensors-01` |
|--------|------|-------|----------------------------------|
| `binary_sensor.enclosure_lid` | binary_sensor | opening | `gpio/enclosure_lid/state` |
| `binary_sensor.leak_detector` | binary_sensor | moisture | `gpio/leak_detector/state` |

**Planned (bus sensors, later phase):**

- I2C environmental sensors → HA **sensor** entities (temperature, humidity, pressure)
- 1-Wire DS18B20 → HA **sensor** per probe address

Discovery prefix: `homeassistant`; device name **Sensor Node**.

## Design decisions

- **`profile: sensors`** — Signals I2C + 1-Wire active; tooling can validate pin conflicts against bus reservations.
- **GPIO inputs on GP6 and GP20** — Avoid GP0/GP1 (I2C) and GP7 (1-Wire); GP20 is a convenient “far” pin on the header for leak rope routing.
- **`pull: down` on leak** — Many leak tapes pull high when wet; idle low reduces false trips.
- **`pull: up` on lid** — Switch to GND when open; standard cabinet tamper pattern.
- **PWM left disabled** — Sensor nodes rarely need GP8–GP15; enable if you add a fan on the enclosure.

## FAQ

**Q: Why enable buses if only GPIO shows in HA?**  
A: This config prepares hardware wiring and bus pin locks before firmware publishes BME280/DS18B20 discovery.

**Q: Can I add a BME280 now?**  
A: Wire it to GP0/GP1; HA entities will appear when the sensor driver phase ships. Until then, GPIO entities still work.

**Q: Multiple DS18B20 on one wire?**  
A: Yes on GP7—standard 1-Wire daisy chain. Discovery will likely emit one entity per ROM address.

**Q: I need SPI display and I2C sensor together.**  
A: Enable SPI in config (GP2–GP5) and keep I2C on GP0/GP1—no overlap. See [full-peripherals.md](full-peripherals.md) for all buses on.

**Q: Can I move 1-Wire off GP7?**  
A: Change `buses.onewire.pin` only if your board profile allows; GP7 is the mqttpi Pico W default.

## Related examples

- [analog-inputs.md](analog-inputs.md) — ADC without sensor buses
- [full-peripherals.md](full-peripherals.md) — I2C + 1-Wire + SPI + I2S + PWM all on
- [level-accelerometer.yaml](level-accelerometer.yaml) — I2C MPU6050 focused example
- [home-assistant.md](home-assistant.md) — binary_sensor patterns

## Implementation status

**Config-only** for GPIO and bus orchestration. I2C/1-Wire sensor HA discovery is **planned**; not in the current repo. **BMS bridge** is fully implemented on Raspberry Pi only.