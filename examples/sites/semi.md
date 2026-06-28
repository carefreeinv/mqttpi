# Semi — 18-Wheel TPMS, Air System & I2S Fleet Alerts

Raspberry Pi 4 template for a **Class 8 tractor**: 18 TPMS wheels (10 tractor + 8 trailer dual axles), sleeper level sensor, fifth wheel / trailer air / connectivity, ABS fault, marker lights, sleeper HVAC, cab accent, UART TPMS receiver, and I2S alert WAVs tied to low pressure events.

**Config file:** [`semi.yaml`](semi.yaml)

---

## Purpose

Give owner-operators and small fleets MQTT/HA visibility into tire pressure across tractor and trailer, critical air/brake connectivity, sleeper leveling, and audible cab alerts for TPMS low, air low, and trailer disconnect—without replacing OEM J1939 dashboards.

---

## Quick Start

```bash
cp examples/sites/semi.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Install SFX in `/opt/mqttpi/sfx/semi/` (01–03).
2. Mount UART TPMS receiver with external antenna; wire TX/RX to GPIO 14/15 (UART0).
3. Replace all 18 `REPLACE_*` sensor IDs—pair while airing up:

```bash
mosquitto_pub -h 192.168.1.50 -t fleet/semi-01/tpms/pair -m "SENSOR_ID"
```

4. Calibrate sleeper MPU6050 on level dock:

```bash
mosquitto_pub -h 192.168.1.50 -t fleet/semi-01/level/calibrate -m "1"
```

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Raspberry Pi 4** (`board: pi4`) |
| Profile | `sensors` |
| Device ID | `semi-tractor-01` |

**Why Pi 4?** 18-wheel TPMS polling, UART + I2C level + I2S alerts, retained MQTT at scale, and reliable operation with truck inverter/APM power.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi 4 | Tractor MQTT hub |
| 433 MHz TPMS UART receiver | GPIO 14 TX / 15 RX, 115200 |
| MPU6050 @ 0x68 | Sleeper level (I2C) |
| I2S DAC/amp | Cab alert tones |
| Opto inputs | Fifth wheel, trailer air, ABS, air low |
| Relay outputs | Marker lights, sleeper HVAC, cab accent |
| 1-Wire (optional) | Reefer or tire hub temps |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Notes |
|-----|---------|-------|
| 1-Wire | Yes | GPIO 4 |
| I2C | Yes | SDA 2, SCL 3 — MPU6050 |
| I2S | Yes | BCLK 18, LRCK 19, DIN 20, DOUT 21 |
| UART0 | TPMS | TX 14, RX 15 |

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 5 | `engine_running` | Engine Running |
| 6 | `fifth_wheel` | Fifth Wheel Locked |
| 16 | `trailer_air` | Trailer Air Connected |
| 17 | `trailer_connected` | Trailer Connected |
| 22 | `abs_fault` | ABS Fault |
| 23 | `marker_lights` | Marker Lights |
| 24 | `sleeper_hvac` | Sleeper HVAC |
| 25 | `cab_accent` | Cab Accent |
| 27 | `air_system_low` | Air System Low |

---

## Sensors

### Level sensor (MPU6050 — sleeper)

| Reading | Alias | Notes |
|---------|-------|-------|
| Pitch | `sleeper_pitch` | mount: `sleeper_floor` |
| Roll | `sleeper_roll` | 5 s publish |
| Level OK | `sleeper_level_ok` | 1.0° threshold |

Calibrate: `fleet/semi-01/level/calibrate`

### TPMS (18 wheels, UART)

**Tractor (10):**

| Axle | Wheels |
|------|--------|
| Steer | FL, FR |
| Drive 1 | Outer L, Inner L, Inner R, Outer R |
| Drive 2 | Outer L, Inner L, Inner R, Outer R |

**Trailer (8):**

| Axle | Wheels |
|------|--------|
| Axle 1 | Outer L, Inner L, Inner R, Outer R |
| Axle 2 | Outer L, Inner L, Inner R, Outer R |

- Tractor low PSI: **95**; trailer: **90**
- Alerts: `low_pressure_sfx: 1` → plays track 1 (`tpms_low_alert`)
- Alert topic: `fleet/semi-01/tpms/alerts`

### BMS / Victron / CAN

**Not in this config.** J1939 CAN would use [`../can-vehicle.yaml`](../can-vehicle.yaml) on a separate node to avoid pin contention with UART TPMS.

### I2S SFX

| # | Alias | File |
|---|-------|------|
| 1 | `tpms_low_alert` | `01-tpms-low.wav` |
| 2 | `air_low_alert` | `02-air-low.wav` |
| 3 | `trailer_disconnect` | `03-trailer-disc.wav` |

Command: `fleet/semi-01/sfx/play`

---

## MQTT / Home Assistant Entities

**Base topic:** `fleet/semi-01`  
**Client ID:** `mqttpi-semi-tractor-01`

| Group | Count |
|-------|-------|
| TPMS pressure/temp/low | 18 wheels |
| Sleeper level | 3 sensors + binary |
| Tractor status | Engine, ABS, Air Low |
| Trailer coupling | Fifth wheel, air, connected |
| Outputs | Markers, HVAC, accent |
| SFX | 3 tracks + auto TPMS alert |

---

## Design Decisions

1. **Pi 4 mandatory** — Wheel count and I2S alerts exceed Pico RAM/CPU comfort zone.
2. **UART0 for TPMS** — Dedicated high-speed receiver stream; I2C only for level.
3. **Separate tractor/trailer PSI thresholds** — Trailer tires often run lower than steer.
4. **`low_pressure_sfx` linkage** — Immediate cab audio without waiting for HA automation latency.
5. **Sleeper level only** — Cab mount IMU would include road pitch; sleeper floor reflects parking comfort.
6. **Fleet base topic** — `fleet/semi-01` supports multi-tractor deployments (`semi-02`, …).

---

## FAQ

**Q: Pairing 18 sensors is tedious.**  
A: Pair one axle per service stop; update YAML `sensor_id` incrementally. Keep a spreadsheet mapping wheel position → ID.

**Q: TPMS misses inner dual wheels.**  
A: Repeater antennas on drive axles; pair inner sensors with valve stems accessible.

**Q: SFX drowned by engine noise.**  
A: Use powered cab speaker on I2S amp; increase WAV gain; trigger only when `engine_running` ON at low speed (HA).

**Q: Trailer wheels when swapping trailers?**  
A: Maintain separate YAML per trailer ID or use HA to disable trailer wheel entities when `trailer_connected` OFF.

**Q: Legal for TPMS vs DOT inspections?**  
A: mqttpi supplements OEM systems; does not replace FMCSA maintenance records.

**Q: Air low GPIO vs TPMS?**  
A: `air_system_low` is chassis air supply switch input; TPMS is per-wheel pressure—both can trigger different SFX (2 vs 1).

---

## Related Examples

| Example | Why |
|---------|-----|
| [`motorhome.yaml`](motorhome.yaml) | 6-wheel I2C TPMS bridge |
| [`rv.yaml`](rv.yaml) | Small vehicle UART TPMS |
| [`cargo-trailer-workshop.yaml`](cargo-trailer-workshop.yaml) | I2S hazard alerts |
| [`../tpms.yaml`](../tpms.yaml) | TPMS pairing |
| [`../can-vehicle.yaml`](../can-vehicle.yaml) | OBD/J1939 add-on |

---

## Open Questions

- Second Pi for J1939 fuel/DEF while keeping TPMS on UART0?
- Trailer ID RFID to auto-load correct 8 wheel sensor IDs?
- Cell MQTT bridge when away from home fleet broker?
- Driver acknowledgment MQTT topic to silence repeating TPMS SFX?
- Integrate weigh station CAT scale BLE for axle weight + TPMS correlation?