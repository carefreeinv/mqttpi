# Victron VE.Can — NMEA 2000 @ 250 kbit/s

## Purpose

Monitor **Victron VE.Can** devices on a **CAN bus at 250 kbit/s** using **29-bit extended frames** and **NMEA 2000 PGNs** (plus Victron-specific data). Publishes DC voltage, current, SOC, solar state, and tank level to MQTT / Home Assistant.

VE.Can uses the same **physical layer** as RV-C (250k, CAN-H/L) but a **different protocol and PGN map**. RV-C decoders **must not** be used on a VE.Can bus.

## Quick start

```bash
cp examples/victron-vecan.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit mqtt.host
# MCP2515 on SPI0 + transceiver → VE.Can CAN-H / CAN-L
# Set protocol: vecan (NOT rvc)
```

**Wiring options:**

- Victron **VE.Can → NMEA2000** cable into a powered NMEA 2000 backbone, or
- MCP2515 / **can2040** tap with correct 250k termination

Run **`protocol: vecan`** separately from any RV-C config ([`can-rvc.md`](can-rvc.md)).

## Hardware

| Item | Spec |
|------|------|
| **Board** | Raspberry Pi Pico W (`profile: sensors`) |
| **CAN controller** | MCP2515 on SPI0 (`backend: mcp2515`) |
| **Transceiver** | Via MCP2515 module + TJA1050 / SN65HVD230 |
| **Bitrate** | **250000** |
| **Frame format** | **Extended** (29-bit) |
| **Protocol** | **`vecan`** (explicit — not `rvc`) |
| **Mode** | `read` (listen-only tap) |

### Typical VE.Can products

| Product | Data |
|---------|------|
| Lynx Shunt VE.Can | DC current, SOC |
| Lynx Smart BMS | Battery management |
| SmartSolar MPPT VE.Can | Solar charger state |
| Multi RS | Inverter/charger |

### MCP2515 pins

| Signal | GPIO |
|--------|------|
| SCK / MOSI / MISO | GP2 / GP3 / GP4 |
| CS | GP5 |
| INT | GP6 |
| Oscillator | 16 MHz |

Alternative: [`can-can2040.md`](can-can2040.md) @ 250k with `protocol: vecan` when firmware supports it.

## Bus wiring

```
MCP2515 + transceiver CANH ───► VE.Can / NMEA 2000 CAN-H (often via M12 backbone)
MCP2515 + transceiver CANL ───► VE.Can / NMEA 2000 CAN-L
Common ground with Victron network negative reference

termination_ohm: 120  → enable only at a physical bus end
```

**VE.Can is NOT RV-C:**

| Bus | Bitrate | Protocol | Example config |
|-----|---------|----------|----------------|
| Victron VE.Can | 250k | NMEA 2000 PGNs + Victron | this file |
| RV-C coach | 250k | RV-C PGN map | [`can-rvc.yaml`](can-rvc.yaml) |
| Vehicle OBD | 500k | ISO 15765 / OBD | [`can-vehicle.yaml`](can-vehicle.yaml) |
| VE.Direct | UART 19200 | Serial text | [`victron-vedirect.yaml`](victron-vedirect.yaml) |

On a Cerbo GX, Victron bridges VE.Can and other ports internally. mqttpi can run **two nodes** or **two protocol stacks** if you tap each bus separately.

## MQTT / Home Assistant topics

Default `base_topic`: `mobile/victron-vecan`

### Listened PGNs

| Alias | PGN | HA name | Unit / class |
|-------|-----|---------|--------------|
| `dc_voltage` | `0x1F214` | DC Voltage (VE.Can) | V |
| `dc_current` | `0x1F213` | DC Current (VE.Can) | A |
| `battery_soc` | `0x1F211` | Battery SOC (VE.Can) | % |
| `solar_state` | `0x1F219` | Solar Charger State | — |
| `tank_level` | `0x1F601` | Tank Level (VE.Can) | % |

`instance: 0` selects the first instance on multi-instance PGNs — adjust per your NMEA 2000 device table.

State pattern: `{base_topic}/victron/{alias}/state` or `{base_topic}/sensors/{alias}/state` (retained, `victron.ve_can.publish.retain: true`)

### Home Assistant discovery

```
homeassistant/sensor/{device_id}_dc_voltage/config
homeassistant/sensor/{device_id}_dc_current/config
homeassistant/sensor/{device_id}_battery_soc/config
…
```

Device: **Victron VE.Can** (manufacturer Victron Energy)

## Design decisions

1. **Explicit `protocol: vecan`** — Prevents accidentally loading RV-C decoders on a Victron energy bus (same bitrate, wrong semantics).
2. **Read-only tap** — Energy monitoring rarely needs TX on VE.Can; reduces risk on a powered NMEA backbone.
3. **NMEA 2000 PGN list** — Aligns with Victron’s VE.Can register documentation; extend `listen` for inverter alarms, DC details, etc.
4. **MCP2515 + 16 MHz crystal** — Matches common breakout boards; `oscillator_hz` must match your module.
5. **Extended frames only** — NMEA 2000 on CAN 2.0B uses 29-bit identifiers.
6. **Not VE.Direct** — UART shunts/solar use [`victron-vedirect.md`](victron-vedirect.md) — simpler wiring for single-device installs.

## FAQ

**Q: Same cable as RV-C?**  
A: **Physical CAN** may look similar (250k, CAN-H/L), but **PGNs differ**. Configuration must set `protocol: vecan` vs `rvc.enabled: true`. Wrong decoder = garbage values.

**Q: Can I merge VE.Can and RV-C in one YAML?**  
A: Only if you operate **two isolated transceivers** on two buses. Do not combine protocols on one decoder context.

**Q: VE.Can vs NMEA 2000 — are they identical?**  
A: VE.Can is Victron’s NMEA 2000-family implementation. Standard PGNs (voltage, current, SOC) interoperate; Victron adds proprietary PGNs documented in their VE.Can manual.

**Q: Why not use VE.Direct instead?**  
A: VE.Direct suits one RJ45 device. VE.Can suits **bussed** Lynx distributors and multiple MPPT units on one backbone.

**Q: Will this control my MultiPlus?**  
A: This example is **listen-only**. Write/command paths for Victron CAN are not defined here; use Victron tooling or future command contracts.

## Related examples

| Example | Relationship |
|---------|--------------|
| [`victron-vedirect.md`](victron-vedirect.md) | UART VE.Direct (not CAN) |
| [`can-rvc.md`](can-rvc.md) | RV-C coach bus (NOT Victron) |
| [`can-can2040.md`](can-can2040.md) | PIO CAN backend @ 250k |
| [`sites/rv-victron.yaml`](sites/rv-victron.yaml) | RV with Victron + optional RV-C |
| [`jbd-bms.md`](jbd-bms.md) | JBD UART BMS (third battery data path) |

## Implementation status

| Component | Status |
|-----------|--------|
| `examples/victron-vecan.yaml` | **Config contract** |
| MCP2515 + `protocol: vecan` decoder | **Not implemented** |
| NMEA 2000 PGN parse (listed PGNs) | **Not implemented** |
| HA discovery publish | **Not implemented** |

**Config contract only.** Do not point RV-C firmware at a Victron VE.Can bus until a dedicated VE.Can decoder ships.