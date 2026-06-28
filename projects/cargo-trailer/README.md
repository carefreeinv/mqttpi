# First project: Cargo trailer

This deployment uses [`examples/sites/cargo-trailer.yaml`](../../examples/sites/cargo-trailer.yaml).

**Documentation:** [`examples/sites/cargo-trailer.md`](../../examples/sites/cargo-trailer.md)

## Status

| Item | State |
|------|-------|
| Target hardware | **Raspberry Pi Pico W** (dedicated node) |
| Config template | `examples/sites/cargo-trailer.yaml` |
| Central MQTT broker | **Not registered yet** — intentional |
| Run on shared Pi 4 | **No** — dev Pi (`carefreeinv` / 192.168.x) already uses most GPIO |
| mqttpi daemon / bridge | **Not started** — no `config.yaml` on this host |

## Why not on this Pi?

The development Pi (`Raspberry Pi 4`) is GPIO-constrained. Cargo trailer I/O belongs on a **separate Pico W** mounted in or near the trailer, talking to the broker over Wi-Fi when you are ready to go live.

## Before go-live checklist

1. [ ] Flash or install mqttpi on a **dedicated Pico W** (not the shared Pi 4).
2. [ ] Audit pins — confirm no overlap with other projects on that board.
3. [ ] `cp examples/sites/cargo-trailer.yaml config.yaml`
4. [ ] `cp secrets.example.yaml secrets.yaml` — set broker host/credentials.
5. [ ] Change `device.id` if `cargo-trailer` collides on the broker.
6. [ ] Wire through 3.3 V level shifters / optocouplers for 12 V trailer signals.
7. [ ] Test with `poll_interval` / dry-run before enabling retained command topics.
8. [ ] Register with central broker only after bench test passes.

## Entities (preview)

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

## MQTT namespace (when enabled)

```
mobile/cargo-trailer/gpio/<alias>/state
mobile/cargo-trailer/gpio/<alias>/set
mobile/cargo-trailer/status
```

Do **not** copy `config.yaml` to the shared Pi root until a dedicated board is assigned.