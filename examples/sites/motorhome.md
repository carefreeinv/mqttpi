# Motorhome — Multi-Zone HVAC, Bays, Level & 6-Wheel TPMS

Pico W template for a Class A or large Class C motorhome: basement bay doors, shore/generator/engine sense, dual-zone HVAC, lighting with PWM, MPU6050 leveling, and six-wheel TPMS via an I2C bridge (steer + dual rear axles).

**Config file:** [`motorhome.yaml`](motorhome.yaml)

---

## Purpose

Consolidate motorhome coach monitoring on one edge node: power source detection (shore/gen), bay security, interior/patio lighting, front/rear HVAC zones, spirit-level sensors, and commercial-grade tire monitoring without sacrificing UART pins.

---

## Quick Start

```bash
cd /home/pi/mqttpi
cp examples/sites/motorhome.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Replace all `REPLACE_*` TPMS sensor IDs after pairing each wheel.
2. Mount MPU6050 flat in center aisle or battery bay (`floor_plane`).
3. Wire 12 V chassis signals through optocouplers; never apply 12 V directly to Pico pins.
4. I2C bus shares MPU6050 (0x68) and TPMS bridge (0x55)—verify cable length and pull-ups.

Pair TPMS:

```bash
mosquitto_pub -h 192.168.1.50 -t mobile/motorhome/tpms/pair -m "SENSOR_ID"
```

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `motorhome-main` |

**Why Pico W?** Sufficient for multi-zone GPIO + I2C sensors; Wi-Fi for mobile HA. TPMS on I2C bridge frees UART and PWM bank.

---

## Hardware List

| Item | Role |
|------|------|
| Pico W | Coach controller |
| MPU6050 @ 0x68 | Level sensor |
| I2C TPMS bridge @ 0x55 | 433 MHz receiver aggregation |
| 1-Wire bus (GP7) | Optional bay/fridge temps |
| Relay board | Lights, HVAC calls |
| Shore/gen/engine dry contacts | Power/running sense |
| Bay door reed switches | Driver/passenger bays |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Notes |
|-----|---------|-------|
| 1-Wire | Yes | GP7 |
| I2C | Yes | GP0/GP1 — level + TPMS bridge |
| PWM | Yes | GP8–15 (living dimmer on GP8) |

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 16 | `entry_door` | Entry Door |
| 2 | `engine_running` | Engine Running |
| 3 | `shore_connected` | Shore Power |
| 4 | `generator_running` | Generator Running |
| 6, 20 | bay doors | Driver / Passenger Bay |
| 21–22, 17–18 | lights | Interior, living, bedroom, patio |
| 19, 26–28 | HVAC | Front fan/cool, rear fan/heat |
| 8 | `living_dim` | Living Dimmer (PWM) |

---

## Sensors

### Level sensor (MPU6050)

| Reading | Threshold |
|---------|-----------|
| Pitch / Roll / Deviation | 2 s publish |
| Level OK | **1.0°** (stricter than RV) |

Calibrate: `mobile/motorhome/level/calibrate`

### TPMS (6 wheels, I2C bridge)

| Position | Alias | Low PSI |
|----------|-------|---------|
| Steer FL/FR | `tpms_steer_fl/fr` | 80 |
| Drive outer/inner L/R | `tpms_drive_*` | 80 |

- Receiver: `i2c`, chip `tpms_bridge`, address `0x55`
- Protocol: `tpms433`
- Pair: `mobile/motorhome/tpms/pair`

### BMS / Victron / CAN / I2S

**Not used** — pair with [`rv-victron.yaml`](rv-victron.yaml) or [`skoolie-bms.yaml`](skoolie-bms.yaml) on a second Pi node for house battery.

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/motorhome`  
**Client ID:** `mqttpi-motorhome-main`

| Group | Count / examples |
|-------|------------------|
| Power | Shore, Generator, Engine |
| Security | Entry, Bay doors |
| Climate | Front/rear HVAC switches |
| Lighting | Interior, accents, patio, dimmer |
| Level | Pitch, Roll, Deviation, Level OK |
| TPMS | 6× pressure/temp/low |

---

## Design Decisions

1. **I2C TPMS bridge** — Shares bus with MPU6050; frees UART1 (used on smaller RV for TPMS).
2. **1.0° level threshold** — Larger coach is more sensitive to twist; adjust per site preference.
3. **1-Wire enabled** — Fridge/bay temperature without extra I2C devices.
4. **Dual HVAC zones** — Separate fan/cool/heat outputs map to front and rear roof units.
5. **Higher TPMS thresholds (80 PSI)** — Motorhome tire pressures exceed travel trailer defaults.

---

## FAQ

**Q: I2C bus lockups with TPMS + MPU6050?**  
A: Short I2C leads, 2.2–4.7 kΩ pull-ups, separate 3.3 V supply filtering. Stagger poll intervals if supported.

**Q: Which wheels are “inner” on duals?**  
A: Inner sensors face the hub; outer face the curb. Label in HA with photos during pairing.

**Q: Shore power shows OFF when connected.**  
A: Invert sense wiring or change `pull`—many inverters use open-collector outputs.

**Q: Can I monitor chassis air brakes?**  
A: Add binary inputs; not in this template. See [`semi.yaml`](semi.yaml) for air system patterns.

**Q: Upgrade from [`rv.yaml`](rv.yaml)?**  
A: Copy GPIO sections, add bay/shore/gen pins, switch TPMS to I2C bridge layout, add wheels.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`rv.yaml`](rv.yaml) | Smaller 4-wheel UART TPMS |
| [`skoolie.yaml`](skoolie.yaml) | Bus conversion exits/solar |
| [`semi.yaml`](semi.yaml) | 18-wheel fleet TPMS |
| [`../tpms.yaml`](../tpms.yaml) | TPMS protocol reference |

---

## Open Questions

- Automatic generator start from shore loss via HA + relay?
- Tag axle TPMS on tag trailers towed behind motorhome?
- RV-C integration for basement lights vs GPIO relays?
- Redundant second Pico for safety-critical bay door alerts?