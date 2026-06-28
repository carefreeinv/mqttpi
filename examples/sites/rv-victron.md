# RV Victron — VE.Direct Solar/Shunt + RV-C Coach Bus

Pico W template for a **high-end RV** combining **Victron VE.Direct** (SmartShunt / MPPT on UART) and **RV-C CAN** (house lights, tank monitors, dimmers) plus GPIO for items not on the coach bus, and MPU6050 leveling.

**Config file:** [`rv-victron.yaml`](rv-victron.yaml)

---

## Purpose

Mirror what a Cerbo GX does in split form: publish Victron battery/solar fields to MQTT/HA, listen and command RV-C devices (tank levels, ceiling dimmers), and handle local GPIO (door, porch light, propane) that may not exist on RV-C.

**Important:** Victron VE.Direct and RV-C are **different buses**—this config wires both intentionally.

---

## Quick Start

```bash
cd /home/pi/mqttpi
cp examples/sites/rv-victron.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Wire VE.Direct UART: Pico GP8 TX / GP9 RX @ 19200 baud to SmartShunt (or MPPT).
2. Wire MCP2515 CAN module on SPI (SCK 2, MOSI 3, MISO 4, CS 5, INT 6) @ 250 kbit RV-C.
3. Enable SPI on Pico; verify CAN termination at coach backbone ends.
4. Set RV-C `source_address: 0x82` unique on bus.
5. Calibrate level: `mobile/rv-victron/level/calibrate`

Second VE.Direct device (e.g. MPPT + shunt) needs another UART or USB on Pi—comment in YAML notes Pi hub option.

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `rv-victron-01` |

**Why Pico W?** CAN via MCP2515 + one VE.Direct UART + I2C level fits with SPI enabled; Wi-Fi to RV router. Heavy multi-UART Victron farms may move to Pi 4.

---

## Hardware List

| Item | Role |
|------|------|
| Pico W | Integration node |
| Victron SmartShunt | VE.Direct battery monitor |
| MCP2515 CAN HAT/module | RV-C @ 250 kbps, 16 MHz crystal |
| MPU6050 @ 0x68 | Level |
| GPIO relays | Porch light, door/propane inputs |
| RV-C backbone | Coach manufacturer network |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Configuration |
|-----|---------|---------------|
| I2C | Yes | GP0 SDA, GP1 SCL — MPU6050 |
| SPI | Yes | Controller 0, SCK 2, MOSI 3, MISO 4, CS 5 |
| CAN (MCP2515) | Yes | INT 6, 250000 bps, extended, `read_write`, protocol `rvc` |
| VE.Direct UART | Yes | UART1, TX 8, RX 9, 19200 baud |
| I2S | No | — |

### CAN / RV-C

| Setting | Value |
|---------|-------|
| Backend | `mcp2515` |
| Oscillator | 16 MHz |
| Bitrate | 250000 |
| Mode | read_write |
| Source address | 0x82 |

### GPIO

| Pin | Alias | HA Name |
|-----|-------|---------|
| 10 | `entry_door` | Entry Door |
| 11 | `porch_light` | Porch Light (GPIO) |
| 14 | `propane_alarm` | Propane Alarm |

---

## Sensors

### Level sensor (MPU6050)

| Reading | Threshold |
|---------|-----------|
| Pitch, Roll | 2 s retained |
| Level OK | 1.5° |

Calibrate: `mobile/rv-victron/level/calibrate`

### Victron VE.Direct

Device alias: `victron_shunt` (SmartShunt on VE.Direct)

| Key | Alias | HA Entity |
|-----|-------|-----------|
| V | `battery_voltage` | House Voltage |
| I | `battery_current` | House Current |
| SOC | `battery_soc` | House SOC |

Configured under top-level `victron.ve_direct` mapping.

### CAN / RV-C

**Listen:**

| PGN | Alias | HA Name |
|-----|-------|---------|
| 0x1FFB9 | `fresh_tank_rvc` | Fresh Tank (RVC) |

**Command:**

| PGN | Alias | Type | HA Name |
|-----|-------|------|---------|
| 0x1FFD8 | `ceiling_light_rvc` | dimmer | Ceiling Light (RVC) |

### TPMS / BMS / I2S

**Not in this file.** Add TPMS from [`rv.yaml`](rv.yaml) only if UART free after VE.Direct—often requires second node.

---

## MQTT / Home Assistant Entities

**Base topic:** `mobile/rv-victron`  
**Client ID:** `mqttpi-rv-victron-01`  
**HA device name:** RV Power & Coach

| Source | Entities |
|--------|----------|
| Victron | House Voltage, Current, SOC |
| RV-C listen | Fresh Tank (RVC) |
| RV-C command | Ceiling Light dimmer |
| GPIO | Entry Door, Porch Light, Propane |
| Level | Pitch, Roll, Level OK |

Topics follow discovery per subsystem (`victron/`, `can/rvc/`, `gpio/`, `sensors/level/`).

---

## Design Decisions

1. **Dual bus architecture** — Documents Cerbo-style separation: VE.Direct ≠ RV-C.
2. **MCP2515 on SPI** — Common for Pico; see [`../can-rvc.yaml`](../can-rvc.yaml) for timing details.
3. **RV-C read_write** — mqttpi can dim ceiling lights while publishing tank PGNs.
4. **GPIO porch light** — Fallback when fixture is not on RV-C; avoids bus discovery gaps.
5. **Single VE.Direct UART** — Comment prompts Pi 4 + USB for second Victron device.
6. **SPI CS shared definition** — CAN uses CS 5; ensure no SPI peripheral conflict.

---

## FAQ

**Q: Cerbo GX already on coach—duplicate data?**  
A: Disable Victron MQTT in VRM or run mqttpi on isolated VLAN for HA-only integration.

**Q: RV-C PGNs differ by manufacturer.**  
A: Update `pgn` and `instance` values from coach documentation or RV-C capture log.

**Q: CAN bus silent.**  
A: Check 120 Ω termination, ground reference, and 250k vs 500k mismatch (RV-C is **250k**).

**Q: VE.Direct SOC wrong.**  
A: Sync SmartShunt capacity and chemistry in Victron app; verify 19200 baud wiring (TX↔RX).

**Q: Add MPPT on same UART?**  
A: VE.Direct is per-device cable—use two UARTs or Victron USB on Pi companion node.

**Q: Merge with [`rv.yaml`](rv.yaml)?**  
A: Combine `pins`, `sensors.level`, and `victron`/`can` blocks; watch GP8/9 UART conflict with TPMS.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`rv.yaml`](rv.yaml) | GPIO coach without CAN |
| [`skoolie-bms.yaml`](skoolie-bms.yaml) | JBD BMS alternative |
| [`../victron-vedirect.yaml`](../victron-vedirect.yaml) | VE.Direct reference |
| [`../can-rvc.yaml`](../can-rvc.yaml) | RV-C protocol |
| [`../victron-vecan.yaml`](../victron-vecan.yaml) | VE.Can NMEA2000 path |

---

## Open Questions

- Auto-discover RV-C device instances vs manual PGN list?
- Bridge Victron SOC to RV-C generator start PGN via HA?
- Pi 4 single node for dual VE.Direct + MCP2515 + TPMS?
- TLS MQTT when publishing SOC off-site?
- Conflict resolution when GPIO porch and RV-C ceiling both exist—which is source of truth?