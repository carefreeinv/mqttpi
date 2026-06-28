# RV — Doors, Tanks, Level, TPMS & Coach I/O

Pico W template for a typical Class C or travel trailer: door/slide/awning sensing, lighting and roof HVAC relays, resistive tank senders, MPU6050 level sensor, and 4-wheel 433 MHz TPMS.

**Config file:** [`rv.yaml`](rv.yaml)

---

## Purpose

Give a mobile RV a single MQTT edge node for coach GPIO, fresh/grey/black tank levels (analog), pitch/roll leveling for campsite setup, and tire pressure/temperature monitoring—all auto-discovered in Home Assistant.

---

## Quick Start

```bash
cp examples/sites/rv.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Replace `REPLACE_FL` / `REPLACE_FR` / `REPLACE_RL` / `REPLACE_RR` TPMS sensor IDs after pairing.
2. Wire 12 V coach signals through level shifters/optocouplers to Pico 3.3 V GPIO.
3. Mount MPU6050 flat on floor plane; calibrate on level pad.
4. Connect 433 MHz TPMS UART receiver to GP8 (TX) / GP9 (RX).

Pair a wheel sensor:

```bash
mosquitto_pub -h 192.168.1.50 -t mobile/rv/tpms/pair -m "SENSOR_ID_HERE"
```

Calibrate level when parked level:

```bash
mosquitto_pub -h 192.168.1.50 -t mobile/rv/level/calibrate -m "1"
```

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `rv-main` |

**Why Pico W?** Low power, compact, Wi-Fi for campground LAN or phone hotspot; enough pins for tanks, GPIO, I2C level, and UART TPMS.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi Pico W | Coach MQTT node |
| MPU6050 (I2C 0x68) | Pitch/roll level |
| 433 MHz TPMS UART receiver | GP8/GP9, 115200 baud |
| Resistive tank senders ×3 | GP26–28 ADC |
| Relay/optocoupler board | Lights, HVAC, 12 V loads |
| Door/slide/awning contacts | GPIO inputs |
| Propane detector (dry contact) | GP20 |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Notes |
|-----|---------|-------|
| I2C | Yes | GP0 SDA, GP1 SCL — **reserved for MPU6050** |
| UART1 | TPMS | TX 8, RX 9 |
| 1-Wire / SPI / I2S | Disabled | — |

### GPIO summary

| Pin | Alias | Function |
|-----|-------|----------|
| 7 | `entry_door` | Door contact |
| 21 | `engine_running` | Engine sense |
| 2 | `slideout_extended` | Slideout |
| 3 | `awning_out` | Awning |
| 4, 6, 10 | lights | Interior, accent, porch |
| 11, 14, 15 | HVAC | Fan, cool, heat |
| 20 | `propane_detector` | Gas alarm |
| 26–28 | tanks | Fresh, grey, black (ADC %) |

---

## Sensors

### Level sensor (MPU6050)

| Reading | Alias | HA Entity | Notes |
|---------|-------|-----------|-------|
| Pitch | `level_pitch` | Level Pitch | ° |
| Roll | `level_roll` | Level Roll | ° |
| Deviation | `level_deviation` | Level Deviation | max_abs |
| Binary | `is_level` | Level OK | threshold 1.5° |

- Mount: `floor_plane`
- Publish: 2 s, retained
- Calibrate: `mobile/rv/level/calibrate`

### TPMS (4 wheels, UART)

| Position | Alias | Low PSI |
|----------|-------|---------|
| FL | `tpms_fl` | 32 |
| FR | `tpms_fr` | 32 |
| RL | `tpms_rl` | 32 |
| RR | `tpms_rr` | 32 |

- Protocol: `tpms433`
- Units: PSI, °F
- Pair topic: `mobile/rv/tpms/pair`

### BMS

**Not used** — see [`skoolie-bms.md`](skoolie-bms.md) or [`rv-victron.md`](rv-victron.md).

### Victron

**Not used** in this file.

### CAN

**Not used.**

### I2S SFX

**Not used.**

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/rv`  
**Client ID:** `mqttpi-rv-main`

| Group | Entities |
|-------|----------|
| Doors / openings | Entry Door, Slideout, Awning |
| Coach | Engine Running, Propane Alarm |
| Lighting / HVAC | Interior, Accent, Porch, Fan, Cool, Heat |
| Tanks | Fresh, Grey, Black (%) |
| Level | Pitch, Roll, Deviation, Level OK |
| TPMS | Pressure/temp/low per wheel ×4 |

Level topics under `{base_topic}/sensors/level_*`; TPMS under `{base_topic}/tpms/{alias}/`.

---

## Design Decisions

1. **UART TPMS on UART1** — Keeps I2C dedicated to MPU6050 without address conflicts.
2. **Analog tanks on GP26–28** — Matches Pico ADC pins; 30 s publish reduces noise.
3. **1.5° level threshold** — Practical for sleeping comfort; tighten in YAML if needed.
4. **Engine debounce 500 ms** — Ignores alternator chatter on ignition sense lines.
5. **PWM disabled** — Saves pins; add dimming on a derivative config if spare GPIO exists.

---

## FAQ

**Q: TPMS wheel not updating.**  
A: Re-pair via `mobile/rv/tpms/pair`, verify receiver antenna placement, confirm sensor ID string matches YAML.

**Q: Tank reads 0% or 100% always.**  
A: Calibrate `scale` min/max to empty/full ADC voltage for your sender kit.

**Q: Level drifts after driving.**  
A: Re-run calibrate when parked; mount IMU on rigid floor panel, not flexible subfloor.

**Q: Can I add solar monitoring?**  
A: Use [`rv-victron.yaml`](rv-victron.yaml) for VE.Direct shunt/MPPT, or add a second node.

**Q: Pico W Wi-Fi at campground?**  
A: Point `mqtt.host` at HA IP on phone hotspot or travel router; use static DHCP lease for Pico.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`motorhome.yaml`](motorhome.yaml) | Larger coach + 6-wheel TPMS via I2C bridge |
| [`trailer.yaml`](trailer.yaml) | Minimal trailer without TPMS/tanks |
| [`camper-top.yaml`](camper-top.yaml) | Truck camper variant |
| [`rv-victron.yaml`](rv-victron.yaml) | Victron + RV-C power bus |
| [`../level-accelerometer.yaml`](../level-accelerometer.yaml) | Level sensor reference |
| [`../tpms.yaml`](../tpms.yaml) | TPMS pairing reference |

---

## Open Questions

- Merge TPMS low-pressure alerts with phone notifications while driving?
- Grey tank overflow prediction from fill rate?
- Second Pico for tow vehicle vs coach bus split?
- Support RV-C dimmers instead of GPIO relays for lights?