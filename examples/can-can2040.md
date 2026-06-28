# CAN can2040 — PIO software CAN controller

## Purpose

Run CAN on a Raspberry Pi Pico W **without an MCP2515** by using the **can2040** library (RP2040 PIO bit-bang) plus an external **CAN transceiver**. Reduces BOM while supporting RV-C @ 250k or OBD @ 500k depending on `bitrate` and decode rules.

This example enables **RV-C** with `read_write` on **GP20/GP21** — the canonical can2040 pin assignment in mqttpi examples.

## Quick start

```bash
cp examples/can-can2040.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit mqtt.host, bitrate (250k RV-C vs 500k OBD)
# Wire transceiver TX/RX to GP21/GP20, CANH/CANL to bus
```

For full RV-C listen/command tables, start from [`can-rvc.yaml`](can-rvc.yaml) and change only the `buses.can` backend block to `can2040`.

## Hardware

| Item | Spec |
|------|------|
| **Board** | Raspberry Pi Pico W (`profile: maximum_gpio`) |
| **CAN MAC** | **can2040** (PIO — no MCP2515) |
| **Transceiver** | TJA1050, SN65HVD230, MCP2551, etc. |
| **PIO GPIO** | RX **GP20**, TX **GP21** |
| **Bitrate (example)** | **250000** (RV-C) |
| **Mode** | `read_write`, `frame_format: extended` |

### What you still need

can2040 replaces the **CAN controller chip**, not the **physical layer transceiver**. You always need a transceiver between GPIO and CAN-H/CAN-L.

### Resource use

- Consumes **one PIO state machine block** on RP2040
- **Two GPIO** (RX/TX) plus transceiver pins
- Pico W **Wi-Fi does not block** can2040 when IRQ latency is kept low

## Bus wiring

```
Pico W GP21 (TX) ──► Transceiver TXD
Pico W GP20 (RX) ◄── Transceiver RXD
Pico GND         ─── Transceiver GND
3V3              ─── Transceiver VIO (3.3 V logic)

Transceiver CANH ──────► Bus CAN-H
Transceiver CANL ──────► Bus CAN-L

Optional 120 Ω between CANH-CANL at bus end (termination_ohm: 120)
```

**Do not** wire GP20/GP21 directly to CAN-H/CAN-L — the transceiver provides differential drive and protection.

### Pin map in this example

| Role | GPIO |
|------|------|
| can2040 RX | **20** |
| can2040 TX | **21** |

SPI is **disabled** — GP2–5 remain free compared to MCP2515 designs.

## MQTT / Home Assistant topics

Default `base_topic`: `mobile/can2040-node-01`

This minimal example only sets:

```yaml
can:
  rvc:
    enabled: true
    source_address: 0x81
```

### Expected topic layout (when merged with RV-C rules)

| Category | Pattern |
|----------|---------|
| Sensor states | `{base_topic}/sensors/{alias}/state` |
| RV-C commands | `{base_topic}/rvc/{alias}/set` |
| Raw/debug frames | `{base_topic}/can/frame` |

Copy `can.rvc.listen` and `can.rvc.command` sections from [`can-rvc.yaml`](can-rvc.yaml) for a complete HA entity set.

### Home Assistant discovery

Follows the same contract as [`can-rvc.md`](can-rvc.md) — device name **CAN2040 Node** until you add `listen`/`command` entries with `ha:` blocks.

## Design decisions

1. **can2040 over MCP2515** — Fewer parts and no SPI bus contention; trades PIO CPU time for simpler wiring.
2. **GP20 / GP21** — Documented mqttpi convention for can2040 RX/TX on Pico W.
3. **250k + extended + RV-C** — Default targets coach RV-C; change `bitrate` to `500000` and swap decode rules for OBD ([`can-vehicle.md`](can-vehicle.md)).
4. **`maximum_gpio` profile** — Keeps PWM pin bank defined but disabled; suitable when the node is CAN-only.
5. **Separate source address (`0x81`)** — Distinct from `0x80` in [`can-rvc.yaml`](can-rvc.yaml) to avoid clashes when both examples are bench-tested on one bus.
6. **IRQ latency warning** — Heavy Wi-Fi + PIO CAN load can drop frames; keep publish loops short.

## FAQ

**Q: can2040 vs MCP2515 — which is better?**  
A: MCP2515 is mature and offloads framing to hardware. can2040 is cheaper and uses GPIO — good when SPI pins are scarce or you want one less chip.

**Q: Are GP20/GP21 fixed?**  
A: They are the **mqttpi example default**, not an RP2040 hardware requirement. can2040 supports other pin pairs if the PIO mapping is updated in firmware.

**Q: Can I run RV-C and Victron VE.Can on one can2040 node?**  
A: **Physically** they may share 250k wiring on some installs, but **protocols differ**. You must run `protocol: vecan` or RV-C decoders separately — never assume cross-decode. See [`victron-vecan.md`](victron-vecan.md).

**Q: Will Wi-Fi break CAN reception?**  
A: Not inherently, but long critical sections or debug logging can miss frames. Test on a bench bus before controlling live loads.

**Q: This YAML has no listen PGNs — is it incomplete?**  
A: It is a **minimal backend reference**. Merge PGN tables from `can-rvc.yaml` or `can-vehicle.yaml` for full MQTT coverage.

## Related examples

| Example | Relationship |
|---------|--------------|
| [`can-rvc.md`](can-rvc.md) | Full RV-C PGN listen/write tables |
| [`can-vehicle.md`](can-vehicle.md) | OBD @ 500k (change bitrate + PIDs) |
| [`victron-vecan.md`](victron-vecan.md) | Victron VE.Can @ 250k (different protocol) |
| [`sites/rv-victron.yaml`](sites/rv-victron.yaml) | Dual-bus RV (Victron + RV-C) |

## Implementation status

| Component | Status |
|-----------|--------|
| `examples/can-can2040.yaml` | **Config contract** |
| can2040 PIO integration | **Not implemented** |
| Transceiver driver (TX/RX GPIO) | **Not implemented** |
| RV-C / OBD decode on can2040 | **Not implemented** |

**Config contract only.** The can2040 backend is specified in YAML; firmware integration is planned. MCP2515 path in [`can-rvc.md`](can-rvc.md) shares the same MQTT contract once implemented.