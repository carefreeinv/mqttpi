# Plan: Fail loudly when the GPIO library is missing instead of silently simulating

- **Value:** high
- **Priority:** P1
- **Slug:** gpio-backend-fail-loud
- **Preferred models:** small, coding-agent
- **Assignee:** ai
- **Depends on:** mqtt-availability-lwt

## Progress
- [x] Step 1: Strict backend selection in `create_backend`
- [x] Step 2: Declare the GPIO library dependency
- [x] Step 3: Clear startup log of the active backend
- [x] Step 4: Docs and changelog
- [ ] Done when holds

## Goal
On real hardware, a missing or broken GPIO library stops mqttpi with a clear error instead of silently falling back to the mock backend, which today makes outputs appear to switch while nothing happens. Mock mode only runs when explicitly requested.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `mqttpi/gpio/backend.py` (`create_backend(force_mock)` catches the `RPi.GPIO` import failure and returns `MockGpioBackend` with a warning), `mqttpi/gpio/manager.py`, `mqttpi/daemon.py` (`--mock-gpio`), `requirements.txt` (no GPIO library listed).

## Depends on (detail)
- `mqtt-availability-lwt` — reuses the pytest harness created there.

## Constraints
- Mock mode is used only with `--mock-gpio` or an explicit config key (e.g. `gpio.backend: mock`); otherwise an import or initialisation failure exits non-zero with an actionable message.
- `RPi.GPIO` becomes a declared dependency for Linux boards using an environment marker (e.g. `RPi.GPIO>=0.7; platform_machine in "armv6l armv7l aarch64"`), so CI on x86 still installs cleanly; if a different library is chosen (e.g. `rpi-lgpio` for newer kernels), record the choice and why.
- Library API: `create_backend()` gains `strict: bool = True`; existing explicit `force_mock=True` keeps working.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Make `create_backend` strict by default; raise a dedicated `GpioBackendUnavailable` error; daemon catches it, logs, exits non-zero | `mqttpi/gpio/backend.py`, `mqttpi/daemon.py`, `tests/test_backend.py` | Unit tests: missing module raises; `force_mock` and `--mock-gpio` still yield the mock | small |
| 2 | Add the GPIO library to `requirements.txt` with a platform marker | `requirements.txt` | `pip install -r requirements.txt` succeeds on x86 CI and installs the library on ARM | small |
| 3 | Log the active backend and board at startup; expose it via an attribute for library users | `mqttpi/gpio/manager.py`, tests | Unit test of the attribute; log line visible with `-v` | small |
| 4 | Document the behavior change and how to run without hardware | `README.md`, `daemon.md`, `CHANGELOG.md` | Docs build passes | small |

## Risks
- Behavior change for users who relied on the silent fallback during development. Mitigation: clear error message naming `--mock-gpio`; changelog entry.
- `RPi.GPIO` is not supported on the newest kernels and boards. Mitigation: note the compatible shim option in docs; keep the backend interface so another library can be swapped in.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- `pytest -q` passes, including the missing-library test
- Starting without the GPIO library and without `--mock-gpio` exits non-zero with a clear message
- Docs and changelog updated

## Handoff
- Branch `feature/gpio-backend-fail-loud`, stacked on `feature/mqtt-resilient-connect`.
- `create_backend(force_mock=False, strict=True, backend=None)` raises `GpioBackendUnavailable` (a `RuntimeError`, so the daemon logs it and exits 1) on import or init failure; the message names `--mock-gpio`, `gpio.backend: mock`, the `gpio` group, and `rpi-lgpio` for Pi 5.
- New config key `gpio.backend` (`rpi` default | `mock`); `GpioManager.backend_name`; startup log `GPIO backend: <name> (board: <board>)`.
- Library choice: `RPi.GPIO` stays the declared dependency (marker: Linux + armv6l/armv7l/aarch64) because it is what the backend imports and what Raspberry Pi OS ships; `rpi-lgpio` documented as the drop-in for Pi 5 / newer kernels (same module name, so they cannot both be listed).
- Breaking change noted in CHANGELOG: the silent mock fallback is gone (`strict=False` restores it for library users).
- Verified: `pytest -q` 51 passed; `pip install --dry-run -r requirements.txt` on x86 skips RPi.GPIO; docs build OK. Not verified: install on ARM (needs a Pi).
