# JBD BMS — wired UART monitor

## Purpose

Monitor a **JBD / Jiabaida** battery management system over a wired UART link and publish pack telemetry to MQTT with **Home Assistant discovery**. Typical use: LiFePO₄ house banks (Overkill Solar, many DIY packs) on a **Raspberry Pi** co-located with the BMS.

This example was **migrated from `~/bms0`** into `mqttpi/bms/` as the first fully implemented protocol bridge in the repo.

## Quick start

```bash
cd /home/pi/mqttpi
cp examples/jbd-bms.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit mqtt.host, bms.port, secrets.yaml credentials

# One-shot test (verbose)
python3 -m mqttpi.bms.bridge --once -v

# Continuous bridge (foreground)
python3 -m mqttpi.bms.bridge -v

# Optional systemd service
sudo cp mqttpi-bms.service /etc/systemd/system/
sudo systemctl enable --now mqttpi-bms.service
```

**Requirements:** Linux with a serial port (`/dev/serial0`, `/dev/ttyUSB0`, etc.). **Pico W cannot run this daemon** — it needs a full Python runtime and blocking UART I/O.

## Hardware

| Item | Notes |
|------|-------|
| **Board** | Raspberry Pi 4 (or any Pi with UART) — `board: pi4` in config |
| **BMS** | JBD / Jiabaida protocol (9600 8N1) — Overkill Solar, many LiFePO₄ packs |
| **Serial** | Pi GPIO UART (`/dev/serial0`) or USB-TTL adapter |
| **Bluetooth module** | **Remove** the BMS Bluetooth dongle from the UART port before wiring |

### UART parameters

| Setting | Value |
|---------|-------|
| Baud | **9600** |
| Data bits | 8 |
| Parity | None |
| Stop bits | 1 (8N1) |
| Response timeout | 2 s (configurable) |
| Poll interval | 30 s (configurable) |

## Bus wiring

Point-to-point 3-wire UART (logic-level TTL, not RS-485):

```
BMS TX  ──►  Pi RX   (GPIO15 / pin 10, or USB-TTL RX)
BMS RX  ◄──  Pi TX   (GPIO14 / pin  8, or USB-TTL TX)
BMS GND ───  Pi GND
```

**Pi UART enable:** If using `/dev/serial0`, ensure the primary UART is enabled and not consumed by the serial console (`raspi-config` → Interface Options → Serial Port).

**USB-TTL:** Set `bms.port: /dev/ttyUSB0` (or the udev symlink you prefer). Cross TX/RX between adapter and BMS as above.

Do **not** connect BMS charge/discharge paths through the Pi — only the low-voltage UART sense lines.

## MQTT / Home Assistant topics

Default `base_topic`: `mqttpi/house-bms` (override in `config.yaml`).

### Availability & summary

| Topic | Payload | Notes |
|-------|---------|-------|
| `{base_topic}/status` | `online` / `offline` | Retained |
| `{base_topic}/bms/state` | JSON summary | SOC, voltage, current, cells, temps, flags |

### Per-sensor state topics

Pattern: `{base_topic}/bms/{key}/state`

| Key | HA entity (example) | Unit |
|-----|---------------------|------|
| `total_voltage` | Total Voltage | V |
| `current` | Current | A |
| `power` | Power | W |
| `soc` | State of Charge | % |
| `capacity_remaining_ah` | Capacity Remaining | Ah |
| `nominal_capacity_ah` | Nominal Capacity | Ah |
| `cycle_count` | Cycle Count | — |
| `min_cell_voltage` | Min Cell Voltage | V |
| `max_cell_voltage` | Max Cell Voltage | V |
| `delta_cell_voltage` | Cell Voltage Delta | V |
| `avg_cell_voltage` | Average Cell Voltage | V |
| `cell_1` … `cell_N` | Cell N Voltage | V |
| `temperature_1` … `temperature_3` | Temperature N | °C |
| `charging` | Charging (binary) | ON/OFF |
| `discharging` | Discharging (binary) | ON/OFF |
| `balancing` | Balancing (binary) | ON/OFF |
| `protection_active` | Protection Active (binary) | ON/OFF |
| `protection_flags` | Protection Flags (text) | string |

### Home Assistant discovery

Published once on first successful poll:

```
homeassistant/sensor/{device_id}_{object_id}/config
homeassistant/binary_sensor/{device_id}_{key}/config
```

Default `device_id`: `jbd_house_pack` (from `bms.ha.device_id`). Device name: **LiFePO4 House Pack**.

## Design decisions

1. **Pi-only runtime** — JBD polling is a long-running Python process with pyserial; RP2040 firmware is not a target for this protocol today.
2. **9600 8N1 fixed default** — Matches factory JBD wiring; higher baud rates are not supported by most packs.
3. **30 s poll interval** — Reduces UART contention and BMS wear; tighten in config if you need faster updates for automation.
4. **Separate from Victron / CAN** — JBD UART is independent of VE.Direct, VE.Can, and RV-C. Many skoolies run JBD for the house pack *and* Victron for solar/shunt on another port.
5. **Migrated topic layout** — Uses `mqttpi/{device-id}` style (not `mobile/`) to stay compatible with the original `bms0` deployment.
6. **Discovery on first good read** — Cell count is taken from the live BMS response so per-cell entities match the actual pack.

## FAQ

**Q: Why must I remove the Bluetooth module?**  
A: JBD exposes a single UART port. The BT module and wired TTL share it — only one listener can be connected at a time.

**Q: Can I run this on Pico W?**  
A: No. Use a Raspberry Pi (or another Linux host with Python 3 and a serial device).

**Q: The bridge reports offline / poll failures — what should I check?**  
A: Verify TX/RX are crossed, GND is common, the correct `/dev/*` path is set, no other process holds the port, and the BMS is awake (some sleep when idle).

**Q: How is this different from Victron SmartShunt monitoring?**  
A: SmartShunt uses **VE.Direct UART @ 19200** (Victron text protocol). JBD uses **9600 8N1** binary framing — different hardware, cable, and decoder. See `victron-vedirect.yaml`.

**Q: Can I monitor two BMS units on one Pi?**  
A: Yes — run two bridge instances with separate configs, serial ports, `device.id`, and `base_topic` values (or two systemd units).

## Related examples

| Example | Relationship |
|---------|--------------|
| [`sites/skoolie-bms.yaml`](sites/skoolie-bms.yaml) | Site template combining house BMS with coach GPIO |
| [`victron-vedirect.yaml`](victron-vedirect.yaml) | Victron shunt/solar on VE.Direct (parallel monitoring) |
| [`victron-vecan.yaml`](victron-vecan.yaml) | Victron Lynx / MPPT on VE.Can CAN bus |
| [`sites/rv-victron.yaml`](sites/rv-victron.yaml) | Full RV: Victron + optional RV-C + GPIO |
| [`level-accelerometer.yaml`](level-accelerometer.yaml) | Coach tilt/level (complements battery monitoring) |

## Implementation status

| Component | Status |
|-----------|--------|
| `examples/jbd-bms.yaml` | **Stable** — reference config |
| `mqttpi/bms/jbd_protocol.py` | **Working** — frame parse |
| `mqttpi/bms/jbd_uart.py` | **Working** — serial client |
| `mqttpi/bms/bridge.py` | **Working** — poll loop + CLI |
| `mqttpi/bms/ha_mqtt.py` | **Working** — HA discovery + state publish |
| `mqttpi-bms.service` | **Working** — systemd unit template |

This is the **only example in this set with shipped Python firmware/bridge code**. All other protocol examples below are **config contracts** awaiting Pico W (or host) runtime implementation.