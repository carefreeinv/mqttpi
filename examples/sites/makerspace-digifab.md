# Makerspace Digifab — Laser, 3D Printers & Electronics Bench

Pico W zone node for digital fabrication: laser room door, motion, **PN532 RFID entry reader**, laser exhaust and cutter outlet, 3D printer bench and vinyl cutter relays, lab and electronics bench lighting with PWM dimming, and lab temperature.

**Config file:** [`makerspace-digifab.yaml`](makerspace-digifab.yaml)

Part of the multi-node makerspace layout — see [`makerspace.md`](makerspace.md).

---

## Purpose

Monitor and control laser cutter safety prerequisites, printer bench power, and electronics lab lighting in a communal digifab area. HA automations interlock laser power with door closed and exhaust running.

---

## Quick Start

```bash
cp examples/sites/makerspace-digifab.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Mount Pico W outside the laser enclosure; use interlock-rated door contacts.
2. Wire laser exhaust contactor before cutter outlet relay.
3. Follow laser OEM and local code for door switches and exhaust prove-out.
4. Deploy mqttpi; device **Makerspace Digifab** appears in HA.

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `makerspace-digifab` |

**Why Pico W?** Digifab is one zone among several; dedicated node keeps laser interlock I/O local to the laser room wiring panel.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi Pico W | Digifab MQTT node |
| Relay module ×6+ | Exhaust, laser, printers, vinyl, lights |
| Interlock door contact | Laser room entry (GP6) |
| PIR motion sensor | Lab motion (GP20) |
| Laser exhaust contactor | GP21 |
| Laser cutter outlet contactor | GP22 |
| NTC thermistor or analog temp transmitter | GP26 |
| PN532 RFID module (I2C) | Member card reader at digifab / laser room entry |
| I2C sensor (future) | BME280 humidity (filament storage), PM2.5 |

---

## Pin / Bus Map

### Buses

| Bus | Enabled | Pins |
|-----|---------|------|
| 1-Wire | No | Pin 7 (reserved) |
| I2C | Yes | SDA 0, SCL 1 — PN532 @ 0x24 |
| RFID IRQ | GP7 | PN532 interrupt (optional) |
| SPI | No | — |
| I2S | No | — |
| PWM | Yes | GP8–15 |

### GPIO

| Pin | Alias | Direction | HA Name |
|-----|-------|-----------|---------|
| 6 | `laser_room_door` | Input (inverted) | Laser Room Door |
| 20 | `motion_lab` | Input | Digifab Motion |
| 21 | `laser_exhaust` | Output | Laser Exhaust |
| 22 | `laser_power` | Output | Laser Cutter Outlet |
| 2 | `printer_bench` | Output | 3D Printer Bench |
| 3 | `vinyl_cutter` | Output | Vinyl Cutter Outlet |
| 4 | `lab_overhead` | Output | Lab Overhead Lights |
| 5 | `electronics_bench` | Output | Electronics Bench |
| 8 | `lab_dim` | PWM | Lab Dimmer |
| 26 | `lab_temp` | Analog input | Digifab Temperature |

---

## RFID (member tracking)

PN532 on I2C at the digifab or laser-room entry. Use HA to gate laser power on certified member UIDs.

| Setting | Value |
|---------|-------|
| Reader | `pn532_i2c` @ **0x24** |
| Zone tag | `digifab` |
| Scan topic | `site/makerspace/digifab/rfid/scan` |
| Access mode | `track` |

See [`../rfid.md`](../rfid.md).

---

## MQTT / Home Assistant Entities

**Base topic:** `site/makerspace/digifab`  
**Client ID:** `mqttpi-makerspace-digifab`

| Entity | Alias | Type |
|--------|-------|------|
| Laser Room Door | `laser_room_door` | binary_sensor (door) |
| Digifab Motion | `motion_lab` | binary_sensor (motion) |
| Laser Exhaust | `laser_exhaust` | switch |
| Laser Cutter Outlet | `laser_power` | switch |
| 3D Printer Bench | `printer_bench` | switch |
| Vinyl Cutter Outlet | `vinyl_cutter` | switch |
| Lab Overhead Lights | `lab_overhead` | switch |
| Electronics Bench | `electronics_bench` | switch |
| Lab Dimmer | `lab_dim` | number (0–100%) |
| Digifab Temperature | `lab_temp` | sensor (°C, 60 s) |
| Last Card UID | `rfid_last_uid` | sensor (text) |
| RFID Scan Count | `rfid_scan_count` | sensor (total_increasing) |
| RFID Access Granted | `rfid_access_granted` | binary_sensor (lock) |

Topic pattern: `{base_topic}/gpio/{alias}/state` (+ `/set` for outputs and dimmer). RFID: `{base_topic}/rfid/*`.

---

## Design Decisions

1. **Laser door as `door` device class** — Distinct entity for interlock automations; inverted pull-up matches closed=safe wiring.
2. **Exhaust before laser power** — Software rule in HA; add hardware exhaust airflow switch (future input on GP7/GP9) for production systems.
3. **Printer bench separate from laser** — 3D printers run without laser interlocks; schedule via HA member-access templates.
4. **Electronics bench lighting** — Low-power relay for solder station area independent of overhead floods.
5. **PN532 entry RFID** — Audit trail for laser room access; HA ties certified UID to `laser_power` scenes.
6. **I2C reserved** — Humidity for filament dry-box alerts, PM sensor for filter maintenance.

---

## FAQ

**Q: How do I interlock the laser?**  
A: HA automation example: `laser_power` may turn ON only when `laser_room_door` is **closed** (binary_sensor off if inverted closed) **and** `laser_exhaust` is ON. Turn `laser_power` OFF immediately if door opens.

**Q: Does mqttpi replace the laser OEM interlock?**  
A: **No.** Use OEM safety chains for certified lasers. This config adds facility-wide MQTT visibility and optional supplemental outlet control.

**Q: Can I add a CNC router here?**  
A: Use a free PWM pin relay or spawn `makerspace-cnc` as another zone node if wiring is in a separate room.

**Q: Vinyl cutter and laser share exhaust?**  
A: HA automation can require `laser_exhaust` ON for `vinyl_cutter` if they share ducting; adjust per your HVAC layout.

**Q: How do I restrict laser access to trained members?**  
A: HA: on `rfid/scan`, if UID in `input_text.laser_certified` → enable laser scene; else notify and log denied entry.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`makerspace.md`](makerspace.md) | Multi-zone architecture overview |
| [`makerspace-woodshop.yaml`](makerspace-woodshop.yaml) | Sibling woodshop zone |
| [`makerspace-welding.yaml`](makerspace-welding.yaml) | Sibling welding zone |
| [`../rfid.md`](../rfid.md) | RFID reader reference |
| [`../garage-door.yaml`](../garage-door.yaml) | Door + relay interlock patterns |