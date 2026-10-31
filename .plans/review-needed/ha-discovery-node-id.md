# Plan: Optional node-id level in Home Assistant discovery topics (per-node broker ACLs)

- **Value:** medium
- **Priority:** P2
- **Slug:** ha-discovery-node-id
- **Preferred models:** small, coding-agent
- **Assignee:** ai
- **Depends on:** mqtt-availability-lwt

## Progress
- [x] Step 1: Add an opt-in discovery topic layout
- [x] Step 2: Apply it to GPIO and BMS publishers
- [x] Step 3: Migration notes and ACL example
- [x] Done when holds

## Goal
Operators can make each device publish its discovery configs under `homeassistant/<component>/<device_id>/<object_id>/config` (the node-id form Home Assistant supports), so a broker ACL can restrict each device to `homeassistant/+/<device_id>/#` and its own `base_topic`. The default stays the current `homeassistant/<component>/<device_id>_<alias>/config`.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `mqttpi/gpio/ha_mqtt.py` (`GpioMqttPublisher` discovery topic), `mqttpi/bms/ha_mqtt.py` (`_discovery_topic`), `config.example.yaml` (`mqtt.homeassistant.discovery_prefix`).
- Home Assistant MQTT discovery topic format: `<discovery_prefix>/<component>/[<node_id>/]<object_id>/config`.

## Depends on (detail)
- `mqtt-availability-lwt` — reuses the pytest harness created there.

## Constraints
- Opt-in key, e.g. `mqtt.homeassistant.discovery_node_id: true`; default off so existing installations keep their entities.
- `unique_id` values unchanged, so Home Assistant keeps entity history when switching layouts.
- Switching layouts must clear the old retained discovery configs (publish empty retained payloads) to avoid duplicates; document it.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Add the config key and a single helper that builds discovery topics | `mqttpi/mqtt/discovery.py` (or similar), `mqttpi/config.py`, tests | Unit tests for both layouts | small |
| 2 | Use the helper in GPIO and BMS publishers; optional cleanup of old-layout retained configs | `mqttpi/gpio/ha_mqtt.py`, `mqttpi/bms/ha_mqtt.py`, tests | Unit tests: topics and unchanged unique ids | small |
| 3 | Document the option with a Mosquitto ACL example | `config.example.md`, `daemon.md`, `CHANGELOG.md` | Docs build passes | small |

## Risks
- Duplicate entities in Home Assistant after switching. Mitigation: cleanup of old retained configs; documented migration.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes for both layouts
- Default layout unchanged (regression test)
- ACL example documented

## Handoff
- Branch `feature/ha-discovery-node-id`, stacked on `feature/bms-shared-connection`. It only needs `mqtt-availability-lwt`; it is stacked because the BMS publisher changed in that branch.
- Done:
  - `mqttpi/mqtt/discovery.py`: `DiscoveryLayout` (`topic`, `stale_topics`) and `parse_discovery_layout(cfg)`.
  - Opt-in keys: `mqtt.homeassistant.discovery_node_id` (`false` default, `true` uses a sanitized `device.id`, or an explicit `[A-Za-z0-9_-]+` id) and `discovery_clear_legacy` (default `true`).
  - GPIO and BMS publishers use the layout. A BMS on a node keeps its device prefix in the object id (`<node>/<bms_id>_<key>`).
  - Legacy cleanup publishes a retained empty payload to the old topic *before* the new config, so HA never sees one unique_id on two topics.
  - `MqttConnection.publish(retain=)` override, so the cleanup is retained even with `mqtt.retain: false`.
- Docs: daemon.md "Discovery topics and per-node ACLs" (topic table, Mosquitto `pattern` ACL, migration and ACL ordering), config.example.md/.yaml, CHANGELOG.
- Verified: 104 passed. Tests cover both layouts, a default-layout regression test, unchanged unique ids, cleanup ordering and retain, sanitizing and validation, and BMS in both layouts.
- Needs a real setup: HA migration on a live install (entity history kept) and a Mosquitto ACL with per-node users.
