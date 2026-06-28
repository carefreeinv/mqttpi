# Cargo trailer deployment

This guide walks through deploying the cargo trailer site template on a dedicated **Pico W** node.

**Config:** [`examples/sites/cargo-trailer.yaml`](../../examples/sites/cargo-trailer.yaml)

**Documentation:** [`examples/sites/cargo-trailer.md`](../../examples/sites/cargo-trailer.md)

## Hardware

| Item | Notes |
|------|-------|
| Board | **Raspberry Pi Pico W** (dedicated node) |
| Config template | `examples/sites/cargo-trailer.yaml` |
| Logic level | 3.3 V — use level shifters / optocouplers for 12 V trailer signals |

Use a dedicated Pico W mounted in or near the trailer. A shared or GPIO-heavy host is a poor fit for this I/O layout.

## Setup checklist

1. [ ] Flash or install mqttpi on a **dedicated Pico W**.
2. [ ] Audit pins — confirm no overlap with other peripherals on that board.
3. [ ] `cp examples/sites/cargo-trailer.yaml config.yaml`
4. [ ] `cp secrets.example.yaml secrets.yaml` — set broker host and credentials.
5. [ ] Change `device.id` if `cargo-trailer` collides on the broker.
6. [ ] Wire through 3.3 V level shifters / optocouplers for 12 V trailer signals.
7. [ ] Test with `poll_interval` / dry-run before enabling retained command topics.
8. [ ] Verify entities in Home Assistant after the bridge publishes discovery payloads.

## Entities

| HA entity | GPIO | Role |
|-----------|------|------|
| `binary_sensor.ramp_door` | GP0 | Ramp door contact |
| `binary_sensor.side_door` | GP1 | Side door |
| `switch.interior_bay` | GP2 | Interior lights |
| `switch.exterior_work` | GP3 | Work light |
| `switch.accent_strip` | GP4 | Accent LEDs |
| `binary_sensor.motion_cargo` | GP6 | PIR / motion |
| `binary_sensor.tie_down_zone` | GP10 | Tie-down armed |
| `binary_sensor.brake_connection` | GP11 | Trailer connected |
| `binary_sensor.temp_probe_alert` | GP20 | High-temp input |

## MQTT namespace

```
mobile/cargo-trailer/gpio/<alias>/state
mobile/cargo-trailer/gpio/<alias>/set
mobile/cargo-trailer/status
```