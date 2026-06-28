# Camper Top — Truck Camper Level, TPMS & Coach I/O

Pico W template for a **truck camper** on a pickup bed: four truck tire TPMS sensors, camper door, MPU6050 level (critical on uneven sites), interior/reading lights, vent fan, furnace, propane/CO inputs, truck engine sense, and house battery voltage ADC.

**Config file:** [`camper-top.yaml`](camper-top.yaml)

---

## Purpose

Integrate truck and camper monitoring on one node: tire pressure for the **pickup** (not dual rear camper wheels unless added), leveling for pop-up or slide camper comfort, 12 V coach lighting/HVAC GPIO, and coarse house battery voltage without a full shunt.

---

## Quick Start

```bash
cp examples/sites/camper-top.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Replace `REPLACE_TRUCK_FL/FR/RL/RR` TPMS IDs after pairing.
2. Mount MPU6050 on camper floor plane; calibrate on level campsite.
3. Scale `house_battery` ADC for your divider (10.5–14.8 V example).

```bash
mosquitto_pub -h 192.168.1.50 -t mobile/camper-top/tpms/pair -m "SENSOR_ID"
mosquitto_pub -h 192.168.1.50 -t mobile/camper-top/level/calibrate -m "1"
```

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `camper-top-01` |

**Why Pico W?** Compact for camper wall mount; Wi-Fi to truck hotspot; UART TPMS + I2C level fits pin budget.

---

## Hardware List

| Item | Role |
|------|------|
| Pico W | Camper MQTT node |
| MPU6050 @ 0x68 | Level (GP0/GP1 I2C) |
| 433 MHz TPMS UART receiver | GP8 TX / GP9 RX |
| Voltage divider | House battery → GP26 ADC |
| Door contact | Camper door GP7 |
| Engine sense from truck | GP2 |
| Propane / CO alarms | GP14, GP15 |
| Relays | Lights, fan, furnace |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Notes |
|-----|---------|-------|
| I2C | Yes | Level sensor |
| UART1 | TPMS | 115200 baud |

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 7 | `camper_door` | Camper Door |
| 2 | `truck_engine` | Truck Engine Running |
| 3 | `interior_main` | Interior Lights |
| 4 | `reading_light` | Reading Light |
| 6 | `vent_fan` | Roof Vent Fan |
| 10 | `accent_strip` | Accent Strip |
| 11 | `furnace_call` | Furnace Call |
| 14 | `propane_alarm` | Propane Alarm |
| 15 | `co_detector` | CO Detector |
| 26 | `house_battery` | House Battery (V) |

---

## Sensors

### Level sensor (MPU6050)

| Reading | Threshold |
|---------|-----------|
| Pitch, Roll, Deviation | 2 s publish |
| Camper Level OK | **2.0°** |

Calibrate: `mobile/camper-top/level/calibrate`

### TPMS (4 truck wheels, UART)

| Position | Low PSI | High PSI |
|----------|---------|----------|
| truck_fl/fr/rl/rr | 35 | 65 |

Pair: `mobile/camper-top/tpms/pair`

### House battery (ADC)

- Pin GP26, 30 s interval
- Scale 10.5–14.8 V (adjust for LiFePO4 or AGM)

### BMS / Victron / CAN / I2S

**Not used.** For accurate SOC use [`rv-victron.yaml`](rv-victron.yaml).

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/camper-top`  
**Client ID:** `mqttpi-camper-top-01`

| Group | Entities |
|-------|----------|
| Truck | Engine Running, 4× TPMS |
| Camper security | Door, Propane, CO |
| Comfort | Lights, Fan, Furnace |
| Level | Pitch, Roll, Deviation, Camper Level OK |
| Power | House Battery voltage |

---

## Design Decisions

1. **TPMS on truck tires only** — Camper does not add duallies in default config; extend `wheels` if needed.
2. **2.0° level threshold** — Truck campers rock more on suspension; tune per chassis.
3. **ADC battery vs shunt** — Simple voltage for “low battery” automations; not coulomb counting.
4. **UART TPMS** — Same layout as [`rv.yaml`](rv.yaml); I2C free for MPU6050 only.
5. **Engine sense from truck** — Disables furnace/120 V inverter automations while driving (HA logic).

---

## FAQ

**Q: Level changes when getting in bed.**  
A: Normal micro-movement; use `level_deviation` smoothed in HA template sensor.

**Q: TPMS on camper spare?**  
A: Add fifth wheel entry in YAML; ensure receiver supports sensor count.

**Q: House battery reads high under charge.**  
A: Voltage-only sensor reflects charge state poorly for LiFePO4—upgrade to Victron shunt.

**Q: Camper off truck for storage?**  
A: Separate `device.id` or disable TPMS automations when disconnected (manual helper in HA).

**Q: vs [`rv.yaml`](rv.yaml)?**  
A: Camper-top drops tanks/slide/awning; adds CO, battery ADC, truck-specific TPMS naming.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`rv.yaml`](rv.yaml) | Full RV coach |
| [`trailer.yaml`](trailer.yaml) | Level without TPMS |
| [`rv-victron.yaml`](rv-victron.yaml) | Accurate battery/solar |
| [`../tpms.yaml`](../tpms.yaml) | Pairing reference |

---

## Open Questions

- Detect camper demount from truck via GPIO or IMU orientation change?
- Merge truck OBD2 speed with level calibrate lockout while moving?
- Second UART for Renogy BT bridge without dropping TPMS?
- Exterior awning GPIO on unused pins?