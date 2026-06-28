# [analog-inputs.yaml](analog-inputs.yaml)

## Purpose / when to use

Three **ADC channels** on **GP26–GP28** (Pico W analog inputs), published to Home Assistant as **sensor** entities with voltage scaling 0.0–3.3 V.

Use for:

- Potentiometers and dimmer feedback
- Light-dependent resistors (with divider)
- Simple voltage monitoring (≤ 3.3 V at the pin)
- Soil moisture or pressure sensors with analog output

Digital buttons and relays belong on other GPIO—see [digital-in-out.md](digital-in-out.md).

## Quick start

```bash
cp examples/analog-inputs.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit device.id, mqtt.host, secrets.yaml
```

**Wiring:** Sensor signal to **GP26**, **GP27**, or **GP28**; reference **GND**; never exceed **3.3 V** on an ADC pin. Use a voltage divider for higher source voltages.

## Board, profile, peripheral toggles

| Setting | Value |
|---------|-------|
| **Board** | `picow` |
| **Profile** | `maximum_gpio` |
| **PWM** | off |
| **All buses** | off |

ADC pins are dedicated; no peripheral toggles consume GP26–GP28 in this example.

## GPIO pool / pin map

| GPIO | Alias | Direction | Publish interval | HA scaling |
|------|-------|-----------|------------------|------------|
| GP26 | `sensor_a0` | analog_input | 5000 ms | 0.0–3.3 V |
| GP27 | `sensor_a1` | analog_input | 5000 ms | 0.0–3.3 V |
| GP28 | `sensor_a2` | analog_input | 5000 ms | 0.0–3.3 V |
| GP0–GP22 | — | digital free | — | — |
| GP29 | — | ADC on die; not broken out on Pico W | — | — |

## MQTT & HA entities expected

| Entity | Type | Unit | Device class | State topic |
|--------|------|------|--------------|-------------|
| `sensor.sensor_a0` | sensor | V | voltage | `mqttpi/analog-01/gpio/sensor_a0/state` |
| `sensor.sensor_a1` | sensor | V | voltage | `.../sensor_a1/state` |
| `sensor.sensor_a2` | sensor | V | voltage | `.../sensor_a2/state` |

HA metadata: `state_class: measurement` for history/graphing.

Raw ADC may be normalized 0.0–1.0 internally; `ha.scale.min/max` maps to **0.0–3.3 V** in discovery and state payloads.

## Design decisions

- **GP26–GP28 only** — Only RP2040 pins with ADC on the Pico W header.
- **`publish.interval_ms: 5000`** — Reduces MQTT chatter for slow-changing analog signals; lower for fast control loops when the agent supports it.
- **`device_class: voltage`** — Honest reporting when using `scale` to volts; change class/unit if you transform values (e.g. percent moisture) in config or HA.
- **maximum_gpio profile** — ADC does not require sensor buses; keeps I2C/1-Wire pins free.
- **No command topics** — Read-only sensors; setpoints live elsewhere.

## FAQ

**Q: Can I read above 3.3 V?**  
A: Not directly. Use a resistor divider or op-amp scale so the pin never exceeds 3.3 V.

**Q: Why 5 s publish interval?**  
A: Default balance for telemetry vs. broker load. Decrease `interval_ms` per pin for faster updates.

**Q: How is `ha.scale` applied?**  
A: Implementation maps raw ADC counts to the min/max range for MQTT state and HA discovery `state_class` display.

**Q: Should I use I2C sensors instead?**  
A: For temperature/humidity (BME280) or precision ADCs, enable I2C in [sensors-i2c-onewire.md](sensors-i2c-onewire.md). Bus-attached sensor HA discovery is planned for a later phase.

**Q: GP26 conflicts with something on my board.**  
A: On bare Pico W, GP26 is ADC0. Some carriers reassign labels—always trace to RP2040 GPIO number.

## Related examples

- [sensors-i2c-onewire.md](sensors-i2c-onewire.md) — Digital sensor buses + GPIO inputs
- [home-assistant.md](home-assistant.md) — Digital HA entity reference
- [maximum-gpio.md](maximum-gpio.md) — Baseline before adding ADC pins
- [level-accelerometer.yaml](level-accelerometer.yaml) — I2C MPU6050 (separate example)

## Implementation status

**Config-only.** ADC sampling, scaling, periodic publish, and HA **sensor** discovery are specified; the Pico W analog input agent is not implemented in this repo yet. **BMS bridge** is the live MQTT implementation.