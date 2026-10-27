# Plan: Pre-actuation command hook so applications can veto or limit MQTT commands

- **Value:** high
- **Priority:** P1
- **Slug:** command-filter-hook
- **Preferred models:** reasoner, coding-agent
- **Assignee:** ai
- **Depends on:** gpio-backend-fail-loud

## Progress
- [ ] Step 1: Design the hook interface
- [ ] Step 2: Route all `/set` commands through it
- [ ] Step 3: Republish true state on reject
- [ ] Step 4: Library entry point for embedding applications
- [ ] Step 5: Docs and examples
- [ ] Done when holds

## Goal
Applications that embed mqttpi (or run alongside it) can inspect every incoming command before any output changes and accept, modify (e.g. clamp a PWM value), or reject it, so local interlocks and safety limits stay in charge while mqttpi still handles MQTT, discovery, and GPIO. Today `GpioManager.handle_mqtt_message` writes outputs directly.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `mqttpi/gpio/manager.py` (`GpioManager.handle_mqtt_message` parses `{base_topic}/gpio/{alias}/set` and writes), `mqttpi/gpio/pins.py` (`PinConfig`), `mqttpi/gpio/ha_mqtt.py` (state publish), `mqttpi/daemon.py` (message fan-out).
- Downstream consumers embedding mqttpi as a library for unattended control need interlocks (e.g. an output must stay off while an input is active) and manual-override precedence without forking mqttpi.

## Depends on (detail)
- `gpio-backend-fail-loud` — same module area (`gpio/`); land the backend change first to avoid conflicting edits; reuses the test harness.

## Constraints
- Hook signature is small and typed, e.g. `CommandFilter = Callable[[CommandRequest], CommandDecision]` where the request carries alias, requested value, source topic, and current state, and the decision is accept, accept-with-value, or reject-with-reason.
- Default behavior with no filter registered is identical to today.
- A rejected or modified command always results in the true output state being published, so Home Assistant does not show a state the hardware is not in.
- Filters may also be declared in config for simple cases (e.g. `pins[].interlock: {alias: ..., when: ON}`) only if the owner approves; otherwise library-only.
- The hook runs on the MQTT callback thread; document that filters must be fast and non-blocking.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python Protocols for `CommandFilter`; immutable dataclasses for request and decision; composition (list of filters, first reject wins).

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Write the interface proposal (types, threading, ordering, error handling) in the plan's Progress and get owner approval | none (plan text) | Owner approval noted in Progress | reasoner + human |
| 2 | Implement `CommandRequest`, `CommandDecision`, filter registration on `GpioManager`, and routing of all `/set` handling through it | `mqttpi/gpio/commands.py`, `mqttpi/gpio/manager.py`, `tests/test_command_filter.py` | Unit tests: accept, clamp, reject, filter exception treated as reject and logged | mid |
| 3 | On reject or modify, publish the actual state and log the reason at info level | `mqttpi/gpio/manager.py`, tests | Unit test: state topic reflects hardware after reject | small |
| 4 | Public library entry point: build a manager from config and register filters without running the stock daemon loop; or let `Daemon` accept filters | `mqttpi/__init__.py`, `mqttpi/daemon.py`, tests | Example script runs with `--mock-gpio` | mid |
| 5 | Document with an interlock example | `daemon.md`, `examples/`, `CHANGELOG.md` | Docs build passes | small |

## Risks
- Filters that block the MQTT thread stall all messages. Mitigation: documented contract; optional timing warning.
- Scope creep into a rules engine. Mitigation: hook only; rules belong to the embedding application.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes with filter tests
- With no filter, existing behavior and topics are unchanged (regression test)
- Example interlock runs against the mock backend
- Docs and changelog updated
