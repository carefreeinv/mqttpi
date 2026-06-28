# CAN vehicle — OBD-II / J1939 read-only

## Purpose

Sniff and **request** standard OBD-II PIDs from a vehicle CAN bus at **500 kbit/s**, publishing decoded values (RPM, speed, coolant temperature) to MQTT for Home Assistant dashboards and automations.

Read-only (`mode: read`) — suitable for OBD port taps and chassis listening without transmitting proprietary write frames.

## Quick start

```bash
cp examples/can-vehicle.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# Edit mqtt.host, verify bitrate matches your vehicle (500k for OBD-II)
# Wire MCP2515 on SPI0 + transceiver to OBD CAN-H/CAN-L
```

**Safety:** DIY vehicle CAN tapping is at your own risk. Prefer listen-only wiring; confirm harness pinout for your make/model.

## Hardware

| Item | Spec |
|------|------|
| **Board** | Raspberry Pi Pico W (`profile: sensors`) |
| **CAN controller** | **MCP2515** on SPI0 (option B: **can2040** — see [`can-can2040.md`](can-can2040.md)) |
| **Transceiver** | TJA1050, SN65HVD230, MCP2551, etc. |
| **Bitrate** | **500000** (OBD-II / ISO 15765-4 high-speed CAN) |
| **Frame format** | Standard + extended (`frame_format: both`) |

### MCP2515 pin map (this example)

| Signal | GPIO |
|--------|------|
| SPI SCK | GP2 |
| SPI MOSI | GP3 |
| SPI MISO | GP4 |
| SPI CS | GP5 |
| MCP2515 INT | GP6 |
| Oscillator | 16 MHz (`oscillator_hz: 16000000`) |

### Termination

`termination_ohm: 120` — enable only if this node is a **physical end** of the vehicle CAN segment. OBD adapters often include termination; duplicate 120 Ω can cause reflection issues.

## Bus wiring

```
MCP2515 module          CAN transceiver          Vehicle / OBD
──────────────          ───────────────          ─────────────
SPI → Pico              CANH ────────────────► CAN-H (pin 6 on OBD-II*)
                        CANL ────────────────► CAN-L (pin 14)
                        GND  ─────────────── common ground

* OBD pinout varies; verify with a wiring diagram. Many ISO 15765-4 vehicles use pins 6/14.
```

**Listen-only:** Config sets `mode: read`. Firmware should configure the transceiver/MCP2515 for receive and controlled OBD requests only — never inject arbitrary frames on a live powertrain bus without understanding the risk.

**Power:** OBD port may supply 12 V — use an isolated or automotive-rated CAN adapter; do not feed 12 V into Pico GPIO.

## MQTT / Home Assistant topics

Default `base_topic`: `mobile/vehicle-can-01`

### Raw frames (optional debug)

| Topic | Payload |
|-------|---------|
| `{base_topic}/can/frame` | Raw CAN frame JSON (retained policy per `can.publish`) |

### Decoded PIDs (requested)

| Alias | OBD PID | Interval | HA name | Unit |
|-------|---------|----------|---------|------|
| `engine_rpm` | `0x0C` | 1000 ms | Engine RPM | rpm |
| `vehicle_speed` | `0x0D` | 1000 ms | Vehicle Speed | km/h |
| `coolant_temp` | `0x05` | 5000 ms | Coolant Temperature | °C |

State topic pattern: `{base_topic}/sensors/{alias}/state`

### Home Assistant discovery

```
homeassistant/sensor/{device_id}_engine_rpm/config
homeassistant/sensor/{device_id}_vehicle_speed/config
homeassistant/sensor/{device_id}_coolant_temp/config
```

Device: **Vehicle CAN**

## Design decisions

1. **MCP2515 default** — Cheapest, well-documented path; SPI uses GP2–6 leaving Wi-Fi intact on Pico W.
2. **500 kbit/s** — ISO 15765-4 high-speed CAN on the OBD-II connector for most passenger/light commercial vehicles.
3. **Request mode for PIDs** — OBD data often requires ISO-TP request/response; passive sniff alone may miss slow broadcast PIDs.
4. **`frame_format: both`** — Some vehicles mix 11-bit OBD IDs with manufacturer extended frames on the same transceiver.
5. **Separate from RV-C / VE.Can** — Vehicle OBD is **not** RV-C (250k J1939-family coach bus) and **not** Victron VE.Can (NMEA 2000 @ 250k).
6. **Read-only mode** — Reduces risk of unintended ECU interactions on stock vehicles.

## FAQ

**Q: 500k or 250k?**  
A: OBD-II on the diagnostic connector is almost always **500 kbit/s**. RV-C and VE.Can use **250 kbit/s** — wrong bitrate = no decode. Use [`can-rvc.yaml`](can-rvc.yaml) or [`victron-vecan.yaml`](victron-vecan.yaml) for 250k networks.

**Q: Can I use can2040 instead of MCP2515?**  
A: Yes — see [`can-can2040.md`](can-can2040.md). Set `backend: can2040`, `rx`/`tx` GPIO, and adjust bitrate for OBD (500k).

**Q: Will this read J1939 on a diesel truck?**  
A: Partially — many PGNs overlap with OBD-request patterns on HD vehicles, but you may need explicit J1939 PGN listen rules instead of OBD PIDs. Extend the `can.listen` list in YAML.

**Q: Is tapping the OBD port legal/safe?**  
A: Read-only monitoring is common for telematics; modifying emissions or safety frames is not. Always verify local regulations and vehicle warranty implications.

**Q: Why km/h for speed?**  
A: OBD PID 0x0D returns km/h per SAE J1979. Convert in HA if you prefer mph (`km * 0.621371`).

## Related examples

| Example | Relationship |
|---------|--------------|
| [`can-can2040.md`](can-can2040.md) | PIO software CAN (no MCP2515) |
| [`can-rvc.md`](can-rvc.md) | RV coach bus @ 250k (different protocol) |
| [`victron-vecan.md`](victron-vecan.md) | Victron NMEA 2000 @ 250k (not OBD) |
| [`tpms.md`](tpms.md) | Tire monitoring (complementary safety) |
| [`sites/semi.yaml`](sites/semi.yaml) | Heavy vehicle site template |

## Implementation status

| Component | Status |
|-----------|--------|
| `examples/can-vehicle.yaml` | **Config contract** |
| MCP2515 driver + OBD request | **Not implemented** |
| ISO-TP / PID decode | **Not implemented** |
| HA discovery publish | **Not implemented** |

**Config contract only** on Pico W. For a working Linux-side bridge in this repo, see [`jbd-bms.md`](jbd-bms.md) (UART, not CAN).