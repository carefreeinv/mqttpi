# Makerspace — Multi-Zone Node Layout

A makerspace is too large for one Pi or Pico W. Deploy **one mqttpi node per shop zone**, each with its own `device.id` and MQTT base topic under `site/makerspace/{zone}`.

**Zone configs:**

| Zone | Config | Doc |
|------|--------|-----|
| Woodshop | [`makerspace-woodshop.yaml`](makerspace-woodshop.yaml) | [makerspace-woodshop.md](makerspace-woodshop.md) |
| Welding / metal | [`makerspace-welding.yaml`](makerspace-welding.yaml) | [makerspace-welding.md](makerspace-welding.md) |
| Digital fabrication | [`makerspace-digifab.yaml`](makerspace-digifab.yaml) | [makerspace-digifab.md](makerspace-digifab.md) |

---

## Purpose

Provide MQTT/HA visibility per shop area: door and motion sensing, **PN532 RFID entry readers** for member tracking, zone lighting, ventilation/dust extraction, and machine outlet relays. Home Assistant ties zones together with automations (dust-on-before-saw, laser interlocks, after-hours lockouts, RFID access rules).

---

## Quick Start

Pick the zone you are wiring first:

```bash
cp examples/sites/makerspace-woodshop.yaml config.yaml
# or makerspace-welding.yaml / makerspace-digifab.yaml
cp secrets.example.yaml secrets.yaml
```

Repeat on additional Pico W boards for other zones. Change `device.id`, `mqtt.base_topic`, and `mqtt.client_id` on each node — the example values are already unique per zone.

---

## Architecture

```
                    ┌─────────────────┐
                    │  MQTT Broker    │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
  site/makerspace/    site/makerspace/    site/makerspace/
     woodshop            welding              digifab
         │                   │                   │
    ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
    │ Pico W  │         │ Pico W  │         │ Pico W  │
    │ dust +  │         │ fume +  │         │ laser + │
    │ saws    │         │ welders │         │ printers│
    └─────────┘         └─────────┘         └─────────┘
```

**Why one node per zone?**

- GPIO and relay count stays within Pico W limits per area
- A fault in one zone does not take down the whole facility
- Wi-Fi placement can follow each shop's RF environment
- HA groups entities by zone device for member-facing dashboards

---

## Board Choice

| Setting | Value (all zones) |
|---------|-------------------|
| Board | **Pico W** (`board: picow`) |
| Profile | `sensors` |
| I2C | Enabled on GP0/GP1 — **PN532 RFID** + future environmental sensors |
| RFID IRQ | GP7 — card-present interrupt (optional) |

Use a **Pi 4** only for facility-wide services (entry mag-lock + PA announcements) — see [`club.yaml`](club.yaml) or [`store.yaml`](store.yaml) patterns for a separate commons node if needed.

---

## RFID — member tracking & access

Each zone node includes a **PN532 reader on I2C** at the shop entry (see [`../rfid.md`](../rfid.md)).

| Zone | Scan topic | `zone` field |
|------|------------|--------------|
| Woodshop | `site/makerspace/woodshop/rfid/scan` | `woodshop` |
| Welding | `site/makerspace/welding/rfid/scan` | `welding` |
| Digifab | `site/makerspace/digifab/rfid/scan` | `digifab` |

**Tracking today:** HA automation on `rfid/scan` JSON → log member UID, update dashboards, correlate with `motion_*` and machine outlet use.

**Access control (HA now, firmware later):** Match UID against a member helper list → pulse mag-lock or enable machine outlets; invalid UID → `rfid/access/denied`. Set `access.mode: track` (default) until firmware allowlist enforcement ships.

**Pair a new fob at a zone reader:**

```bash
mosquitto_pub -h 192.168.1.50 -t site/makerspace/woodshop/rfid/pair -m "ON"
```

---

## Cross-Zone Automations (HA)

Examples to implement in Home Assistant, not in mqttpi firmware:

| Rule | Trigger / condition |
|------|---------------------|
| Dust before saw | `table_saw_power` ON only when `dust_collector` is ON |
| Welder ventilation | `welder_outlet_*` ON only when `fume_extractor` is ON |
| Laser interlock | `laser_power` ON only when `laser_room_door` closed **and** `laser_exhaust` ON |
| After hours | Block machine outlets outside member-access schedule |
| RFID + mag-lock | Valid UID on `rfid/scan` → energize commons `entry_lock` relay |
| Laser room ACL | Digifab `rfid/scan` with laser-certified UID → allow `laser_power` scene |
| Vacant zone lights | Turn off `shop_overhead` / `lab_overhead` after motion clears + timeout |

---

## Related Examples

| Example | Why |
|---------|-----|
| [`workshop.yaml`](workshop.yaml) | Single-owner shop; one node covers everything |
| [`club.yaml`](club.yaml) | Facility entry, mag-lock, PA — separate commons node |
| [`../rfid.md`](../rfid.md) | PN532 wiring, MQTT topics, access hooks |
| [`../multi-relay.yaml`](../multi-relay.yaml) | Relay output patterns |
| [`../relay-bank-16.yaml`](../relay-bank-16.yaml) | More outlets per zone via native GPIO |

---

## Open Questions

- Dedicated `makerspace-commons` node for front entry, member mag-lock, and class-room lighting?
- Central dust collector on its own node vs woodshop-local collector relay?
- BACnet/Modbus bridge for large VFD dust or welding fume systems?
- Per-machine INA219 current clamps on I2C for overload alerts?
- `makerspace-commons` node with Wiegand front-door reader vs PN532 zone entries?
- Firmware `access.mode: allowlist` with signed member roster sync?