# Plan: CAN bus support on Linux via SocketCAN (MCP2515-class controllers)

- **Value:** medium
- **Priority:** P3
- **Slug:** can-socketcan-driver
- **Preferred models:** reasoner, coding-agent
- **Assignee:** ai
- **Depends on:** ha-numeric-sensor-entities

## Progress
- [ ] Step 1: Decide scope with the owner (raw frames, RV-C decode, both)
- [x] Step 2: SocketCAN transport
- [x] Step 3: Frame-to-entity mapping from config
- [ ] Step 4: Docs and test on `vcan0`
- [ ] Done when holds

## Goal
The documented `buses.can` config contract works on Linux boards with an SPI CAN controller (MCP2515-class, exposed as SocketCAN): configured frames are decoded into numeric or binary entities and published through the shared sensor entities; sending frames is optional and goes through the command filter.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `examples/can-rvc.yaml`, `examples/can-vehicle.yaml`, `examples/can-can2040.yaml` (Pico W path, out of scope here), `config.example.yaml` (`buses.can`: `backend`, `bitrate`, `mode`), `mqttpi/sensors/` (from `ha-numeric-sensor-entities`).

## Depends on (detail)
- `ha-numeric-sensor-entities` — decoded values publish as numeric sensor entities.

## Constraints
- Linux SocketCAN only (`python-can` as an optional extra); interface bring-up (`ip link set can0 up type can bitrate ...`) documented, not performed by mqttpi unless the owner wants it.
- Read-only by default; transmit requires explicit config and passes through the command filter.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Record the scope decision (generic frame mapping first; RV-C decoding later or now) in Progress | none (plan text) | Owner approval noted | reasoner + human |
| 2 | SocketCAN reader thread with timeouts and reconnect | `mqttpi/can/transport.py`, tests on `vcan0` | Tests pass on Linux CI with `vcan` | mid |
| 3 | Config-driven frame mapping (id, byte offset, length, scale, unit) to entities | `mqttpi/can/mapping.py`, tests | Unit tests | mid |
| 4 | Docs and changelog | `daemon.md`, `config.example.md`, `CHANGELOG.md` | Docs build passes | small |

## Risks
- Bus-off states on misconfigured bitrate. Mitigation: detect and log; restart interface guidance in docs.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes, including `vcan0` tests on Linux
- `examples/can-rvc.yaml` (mapped subset) runs against `vcan0`
- Docs and changelog updated

## Handoff

- **Implemented** (branch `feature/can-socketcan-driver`, stacked on `feature/mcp23017-expander-driver`):
  - `mqttpi/can/transport.py`: stdlib `AF_CAN`, no new dependency. One reader thread per interface, with reconnect/backoff and bus-off logging.
  - `mqttpi/can/mapping.py`: the `type: can_frame` sensor driver.
  - `examples/can-frames.yaml` / `.md`, plus sections in daemon.md and config.example.md.
- **Step 1 left open: the owner picks the scope.** Implemented the conservative default: generic, read-only raw-frame mapping (id or J1939-style PGN). RV-C decoding and transmit are not implemented; `can-rvc.yaml` is still a contract.
- **Step 4 partly done.** The docs are written, and the unit tests use a fake transport. The `vcan0` round-trip test exists but was **skipped**: the dev box has no `vcan` kernel module.
  - On a Pi: `sudo modprobe vcan && sudo ip link add dev vcan0 type vcan && sudo ip link set up vcan0 && pytest tests/test_can.py`.
- **Bench:**
  - MCP2515 HAT or USB adapter at 250 kbit/s, with `candump` alongside;
  - check the decoded values against a known device;
  - pull the termination or use a wrong bitrate, and confirm the bus-off log and recovery (`restart-ms 100`);
  - `ip link set can0 down`/`up` while running, and confirm the reader reconnects.
