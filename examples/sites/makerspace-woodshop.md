# Makerspace Woodshop — Dust, Saws & Lighting

Pico W zone node for a communal woodshop: shop door, motion, **PN532 RFID entry reader**, central dust collector, table saw / planer / bandsaw outlet relays, overhead and bench lighting with PWM dimming, and shop temperature.

**Config file:** [`makerspace-woodshop.yaml`](makerspace-woodshop.yaml)

Part of the multi-node makerspace layout — see [`makerspace.md`](makerspace.md).

---

## Purpose

Monitor and control one woodshop bay in a larger makerspace. Machine outlets are MQTT switches; HA automations enforce safety rules (dust collector before saws, after-hours lockouts) across this zone and optionally other zones.

---

## Quick Start

```bash
cp examples/sites/makerspace-woodshop.yaml config.yaml
cp secrets.example.yaml secrets.yaml
```

1. Mount Pico W in the woodshop enclosure; use 3.3 V–compatible relay boards.
2. Wire shop door contact, PIR motion, and machine outlet relays per pin map.
3. Calibrate `shop_temp` ADC scale to your probe.
4. Deploy mqttpi; device **Makerspace Woodshop** appears in HA.

---

## Board Choice

| Setting | Value |
|---------|-------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| Device ID | `makerspace-woodshop` |

**Why Pico W?** Low cost per zone; enough GPIO for three machine outlets, dust collector, lighting, and one ADC channel.

---

## Hardware List

| Item | Role |
|------|------|
| Raspberry Pi Pico W | Woodshop MQTT node |
| Relay module ×6+ | Dust collector, saws, overhead, bench |
| Magnetic door contact | Woodshop entry |
| PIR motion sensor | Shop motion (GP20) |
| NTC thermistor or analog temp transmitter | GP26 |
| PWM LED driver (optional) | Overhead dimmer on GP8 |
| PN532 RFID module (I2C) | Member card reader at woodshop entry |
| I2C sensor (future) | INA219 per machine circuit, BME280 |

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
| 6 | `shop_door` | Input (inverted) | Woodshop Door |
| 20 | `motion_shop` | Input | Woodshop Motion |
| 21 | `dust_collector` | Output | Dust Collector |
| 22 | `table_saw_power` | Output | Table Saw Outlet |
| 2 | `planer_power` | Output | Planer Outlet |
| 3 | `bandsaw_power` | Output | Bandsaw Outlet |
| 4 | `shop_overhead` | Output | Overhead Lights |
| 5 | `bench_lights` | Output | Bench Accent |
| 8 | `overhead_dim` | PWM | Overhead Dimmer |
| 26 | `shop_temp` | Analog input | Woodshop Temperature |

### MQTT aliases

| Key | Maps to |
|-----|---------|
| `overhead_bank` | `shop_overhead` |

---

## RFID (member tracking)

PN532 on I2C at the woodshop entry door. Publishes scan events for HA logging and future access rules.

| Setting | Value |
|---------|-------|
| Reader | `pn532_i2c` @ **0x24** |
| Zone tag | `woodshop` |
| Scan topic | `site/makerspace/woodshop/rfid/scan` |
| Last UID | `site/makerspace/woodshop/rfid/last_uid/state` |
| Access mode | `track` (HA ACL today; firmware allowlist later) |

See [`../rfid.md`](../rfid.md) for wiring, pair mode, and mag-lock automations.

---

## MQTT / Home Assistant Entities

**Base topic:** `site/makerspace/woodshop`  
**Client ID:** `mqttpi-makerspace-woodshop`

| Entity | Alias | Type |
|--------|-------|------|
| Woodshop Door | `shop_door` | binary_sensor (door) |
| Woodshop Motion | `motion_shop` | binary_sensor (motion) |
| Dust Collector | `dust_collector` | switch |
| Table Saw Outlet | `table_saw_power` | switch |
| Planer Outlet | `planer_power` | switch |
| Bandsaw Outlet | `bandsaw_power` | switch |
| Overhead Lights | `shop_overhead` | switch |
| Bench Accent | `bench_lights` | switch |
| Overhead Dimmer | `overhead_dim` | number (0–100%) |
| Woodshop Temperature | `shop_temp` | sensor (°C, 60 s) |
| Last Card UID | `rfid_last_uid` | sensor (text) |
| RFID Scan Count | `rfid_scan_count` | sensor (total_increasing) |
| RFID Access Granted | `rfid_access_granted` | binary_sensor (lock) |

Topic pattern: `{base_topic}/gpio/{alias}/state` (+ `/set` for outputs and dimmer). RFID: `{base_topic}/rfid/*`.

---

## Design Decisions

1. **Zone-scoped base topic** — `site/makerspace/woodshop` keeps MQTT and HA devices separate from welding and digifab nodes.
2. **Three machine outlets** — Covers typical communal woodshop tools; add relays or a second node if you need jointer, drum sander, etc.
3. **Dust collector as switch, not interlock** — HA enforces "dust on before saw"; allows one collector serving multiple zones via automation.
4. **PN532 on I2C** — Shares GP0/GP1 with future sensors; avoids SPI pins used by machine relays.
5. **RFID `track` mode** — Every tap logged; HA matches UID to member roster for access and usage reports.
6. **60 s temperature publish** — Adequate for comfort/HVAC; reduces MQTT chatter.

---

## FAQ

**Q: How do I enforce dust-on-before-saw?**  
A: HA automation: allow `table_saw_power`, `planer_power`, and `bandsaw_power` ON only when `dust_collector` is ON.

**Q: Can one dust collector serve multiple zones?**  
A: Yes — put the collector relay on whichever zone hosts the motor, then reference that switch in other zones' automations.

**Q: Difference vs [`workshop.yaml`](workshop.yaml)?**  
A: Workshop is a **single-owner** fixed shop on one node. Makerspace woodshop is a **zone node** in a multi-board facility with more machine outlets and zone-scoped MQTT topics.

**Q: Need more than ~10 relays in the woodshop?**  
A: Add a second Pico W node (e.g. `makerspace-woodshop-b`) or use [`relay-bank-16.yaml`](../relay-bank-16.yaml) / MCP23017 expanders.

**Q: How do I log who used the table saw?**  
A: Correlate `rfid/scan` events with `table_saw_power` ON in HA — scan topic includes `zone: woodshop` and card UID.

**Q: Can RFID unlock the woodshop door?**  
A: Yes via HA: valid UID on `rfid/scan` → pulse a mag-lock relay. See [`../rfid.md`](../rfid.md) and [`club.yaml`](club.yaml) for lock patterns.

---

## Related Examples

| Example | Why |
|---------|-----|
| [`makerspace.md`](makerspace.md) | Multi-zone architecture overview |
| [`makerspace-welding.yaml`](makerspace-welding.yaml) | Sibling metal shop zone |
| [`makerspace-digifab.yaml`](makerspace-digifab.yaml) | Sibling laser/3D-print zone |
| [`workshop.yaml`](workshop.yaml) | Single-shop variant |
| [`../rfid.md`](../rfid.md) | RFID reader reference |
| [`../analog-inputs.yaml`](../analog-inputs.yaml) | ADC scaling reference |