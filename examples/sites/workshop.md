# Workshop — Tools, Dust Collection & Machine Interlocks

Pico W site template for a fixed workshop: bay door, motion, machine power relays, overhead/bench lighting with PWM dimming, and an analog temperature probe.

**Config file:** [`workshop.yaml`](workshop.yaml)

---

## Purpose

Provide MQTT/HA visibility and control for a small shop: door and motion sensing, dust collector and table-saw outlet relays, overhead and bench lighting, and periodic shop temperature readings from an analog probe.

---

## Quick Start

```bash
cd /home/pi/mqttpi
cp examples/sites/workshop.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Power Pico W from a 5 V supply; level-shift or use 3.3 V–compatible relay boards for machine circuits.
2. Wire bay door contact, PIR motion, and relay outputs per pin map.
3. Calibrate `shop_temp` ADC scale to your thermistor or 0–10 V transmitter.
4. Flash/deploy mqttpi; device appears as **Workshop** in HA.

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `workshop-main` |

**Why Pico W?** Low cost, Wi-Fi onboard, enough GPIO for relays and one ADC channel. Fixed workshop with local Wi-Fi; no need for Pi-class audio or USB.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi Pico W | MQTT GPIO node |
| Relay module ×4+ | Dust collector, table saw, overhead, bench lights |
| Magnetic reed or limit switch | Bay door |
| PIR motion sensor | Shop motion (GP20) |
| NTC thermistor or analog temp transmitter | GP26 analog input |
| PWM LED driver (optional) | Overhead dimmer on GP8 |
| I2C sensor (future) | Bus reserved on GP0/GP1 |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Pins |
|-----|---------|------|
| 1-Wire | No | Pin 7 (reserved) |
| I2C | Yes | SDA 0, SCL 1 |
| SPI | No | — |
| I2S | No | — |
| PWM | Yes | GP8–15 |

### GPIO

| Pin | Alias | Direction | HA Name |
|-----|-------|-----------|---------|
| 6 | `bay_door` | Input (inverted) | Bay Door |
| 20 | `motion_shop` | Input | Shop Motion |
| 21 | `dust_collector` | Output | Dust Collector |
| 22 | `table_saw_power` | Output | Table Saw Outlet |
| 2 | `shop_overhead` | Output | Overhead Lights |
| 3 | `bench_lights` | Output | Bench Accent |
| 8 | `overhead_dim` | PWM | Overhead Dimmer |
| 26 | `shop_temp` | Analog input | Shop Temperature Probe |

### MQTT aliases

| Key | Maps to |
|-----|---------|
| `overhead_bank` | `shop_overhead` |
| `bench_strip` | `bench_lights` |

---

## Sensors

### Level sensor

**Not used.**

### TPMS

**Not used.**

### BMS

**Not used.**

### Victron

**Not used.**

### CAN

**Not used.**

### I2S SFX

**Not used** — see [`house.md`](house.md) or [`cargo-trailer-workshop.md`](cargo-trailer-workshop.md) for Pi 4 I2S setups.

---

## MQTT / Home Assistant Entities

**Base topic:** `site/workshop`  
**Client ID:** `mqttpi-workshop-main`

| Entity | Alias | Type |
|--------|-------|------|
| Bay Door | `bay_door` | binary_sensor (garage_door) |
| Shop Motion | `motion_shop` | binary_sensor (motion) |
| Dust Collector | `dust_collector` | switch |
| Table Saw Outlet | `table_saw_power` | switch |
| Overhead Lights | `shop_overhead` | switch |
| Bench Accent | `bench_lights` | switch |
| Overhead Dimmer | `overhead_dim` | number (0–100%) |
| Shop Temperature Probe | `shop_temp` | sensor (°C, 60 s interval) |

Topic pattern: `{base_topic}/gpio/{alias}/state` (+ `/set` for outputs and dimmer).

---

## Design Decisions

1. **Pico W for cost and Wi-Fi** — Workshop is stationary; no Pi overhead required.
2. **I2C enabled, unused** — Reserved for INA219 current monitors or BME280 without reflash.
3. **Full PWM bank enabled** — Future servo blast gates or extra dimmers on GP9–15.
4. **Machine outlets as switches, not interlocks** — HA automations enforce “dust on before saw” rules.
5. **60 s temperature publish** — Reduces MQTT chatter; adequate for HVAC/comfort monitoring.

---

## FAQ

**Q: How do I enforce “dust collector before table saw”?**  
A: HA automation: allow `table_saw_power` ON only when `dust_collector` is ON; optionally alert on violation.

**Q: Analog temperature reads wrong.**  
A: Adjust `scale: { min: -40.0, max: 85.0 }` to match your probe. Verify divider resistor and reference voltage.

**Q: Can I run 240 V machine circuits?**  
A: Use properly rated external contactors; Pico only drives low-voltage relay coils. Follow electrical code.

**Q: Motion sensor false triggers.**  
A: Increase `debounce_ms` (currently 200) or aim PIR away from HVAC airflow.

**Q: Difference vs cargo-trailer-workshop?**  
A: This is a **fixed** Pico W shop without I2S. Cargo-trailer-workshop is a **mobile** Pi 4 shop with SFX and shore power sense.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`cargo-trailer-workshop.yaml`](cargo-trailer-workshop.yaml) | Mobile shop + I2S alerts |
| [`cargo-trailer.yaml`](cargo-trailer.yaml) | Enclosed trailer GPIO only |
| [`../multi-relay.yaml`](../multi-relay.yaml) | Relay output patterns |
| [`../analog-inputs.yaml`](../analog-inputs.yaml) | ADC scaling reference |
| [`../pwm-bank.yaml`](../pwm-bank.yaml) | PWM channel details |

---

## Open Questions

- Add I2C current clamps per machine circuit for overload detection?
- E-stop input wired to kill all relay outputs via hardware interlock?
- Integrate shop air quality (PM2.5) on I2C?
- BACnet or Modbus bridge for larger dust collector VFD?