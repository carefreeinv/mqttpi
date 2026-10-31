# Plan: pip packaging (`pyproject.toml`) and publish the release tags the changelog references

- **Value:** high
- **Priority:** P2
- **Slug:** packaging-and-release-tags
- **Preferred models:** small, terminal-agent
- **Assignee:** ai
- **Depends on:** none

## Progress
- [x] Step 1: Add `pyproject.toml` with console scripts
- [x] Step 2: Single-source the version
- [ ] Step 3: Confirm which commits the existing changelog versions correspond to
- [ ] Step 4: Create and push the missing tags (human)
- [x] Step 5: Install docs and release checklist
- [x] Done when holds

## Goal
mqttpi can be installed and pinned like any Python package (`pip install mqttpi @ git+https://github.com/carefreeinv/mqttpi@v0.3.0`), and every version in `CHANGELOG.md` has a matching git tag, so the compare links work and downstream projects can depend on a version instead of a commit.

## Context read
- `.anchor/ANCHOR.md`, `.anchor/templates/plan.md`, `.plans/README.md`, `.anchor/conventions.md`
- `README.md`, `daemon.md`, `config.example.md`, `config.example.yaml`, `CHANGELOG.md` (public contract: config keys, MQTT topics, HA discovery)
- `requirements.txt`, `mqttpi/__init__.py` (`__version__ = "0.2.0"`), `mqttpi/__main__.py`, `mqttpi/bms/bridge.py` (`main`), `mqttpi.service`, `mqttpi-bms.service` (paths assume a clone in `%h/mqttpi`), `README.md` install section.
- `CHANGELOG.md` links `v0.1.0` through `v0.2.0`, but the repository has no tags. Candidate commits from history (owner to confirm): `v0.1.0` = `5feef11` ("Initial public release v0.1.0"), `v0.1.1` = `042d779`, `v0.1.2` = `e88174d`, `v0.1.3` = `5aef1e9`, `v0.2.0` = `8998f0b` ("Add unified mqttpi daemon (GPIO + BMS) v0.2.0").

## Constraints
- Do not rewrite history; tags point at existing commits.
- Keep `requirements.txt` and the clone-based install working (systemd templates reference it).
- Runtime dependencies in `pyproject.toml` match `requirements.txt`; dev and docs extras optional.
- Publishing to PyPI is out of scope unless the owner asks; git tags plus a buildable wheel are the goal.
- Tag creation and push is a human step (or an explicitly approved one); agents only prepare the list.
- Pure library and daemon change only; no breaking change to existing configs without an explicit opt-in key.
- Stay compatible with the Python versions the code base supports today (no minimum is declared yet; `packaging-and-release-tags` sets `requires-python`); no new runtime dependency unless listed here.

## Conventions
Python per `.anchor/conventions.md`: small composable classes, Protocols or narrow ABCs, dependency injection over globals; pytest for tests; user-facing changes documented in `README.md`/`daemon.md`/`config.example.md` and `CHANGELOG.md` `[Unreleased]` when they ship.

## Steps
| # | Task | Touches | Verify by | Route to |
|---|------|---------|-----------|----------|
| 1 | Add `pyproject.toml` (setuptools or hatchling), package discovery for `mqttpi*`, console scripts `mqttpi` and `mqttpi-bms`, `requires-python` set to the verified minimum, and `requires-python` set to the verified minimum | `pyproject.toml` | `python -m build` produces a wheel; `pip install dist/*.whl` then `mqttpi --help` works in a clean venv | small |
| 2 | Single-source the version from `mqttpi/__init__.py`; move pytest config into `pyproject.toml` if `pytest.ini` exists | `pyproject.toml`, `pytest.ini` | `pip show mqttpi` reports the version; `pytest -q` still runs | small |
| 3 | Verify each candidate commit against the changelog entry (version string in code or changelog at that commit) and record the final list in Progress | none (plan text) | Owner approval noted in Progress | human |
| 4 | Create annotated tags `v0.1.0` to `v0.2.0` on the approved commits and push them | git tags only | `git ls-remote --tags origin` lists them; changelog compare links resolve | human |
| 5 | Document pip install and pinning; add a short release checklist (bump version, changelog, tag) | `README.md`, `CONTRIBUTING.md` or `daemon.md`, `CHANGELOG.md` | Docs build passes | small |

## Risks
- Wrong tag targets are public and confusing. Mitigation: owner-approved list before tagging.
- systemd units assume a clone path. Mitigation: document both install paths; unit paths unchanged in this plan.

## Escalation triggers
- Ambiguous requirement discovered → back to planner
- Task fails verification twice → bigger model
- Architectural decision needed → bigger model / human
- A change would alter documented config keys, topics, or payloads for existing users → owner decides; keep backward compatible by default and record it under `[Unreleased]` in `CHANGELOG.md`
- Step looks overqualified for its assigned tier (boilerplate/rename/formatting on a frontier route) → downgrade to smaller/local model instead

## Done when
- Wheel builds and installs in a clean venv; both console scripts run
- All changelog versions have tags on origin and compare links resolve
- Install docs updated; docs build passes

## Handoff
- Branch `feature/packaging-and-release-tags`, stacked on `feature/mqtt-tls`.
- Done:
  - `pyproject.toml` (setuptools).
    - Package discovery for `mqttpi*`.
    - Console scripts `mqttpi` → `mqttpi.daemon:main` and `mqttpi-bms` → `mqttpi.bms.bridge:main`.
    - `requires-python >= 3.9`, verified: the wheel was built and installed in a clean 3.9.25 venv, `mqttpi --help` and `mqttpi-bms --help` work, `pip show` reports 0.2.0, and the unit tests pass on 3.9.
    - Version is dynamic from `mqttpi.__version__`.
    - Extras: `dev` (pytest, amqtt on 3.10+) and `docs`.
  - `pytest.ini` moved into `[tool.pytest.ini_options]`.
  - README: package install, pinning, test/wheel commands, and a release checklist.
  - A test asserts that the pyproject dependencies match `requirements.txt`.
- **Step 3 (owner approval) is pending.** Verified candidate list: the version string in `CHANGELOG.md`, and in `__version__` where it was bumped, at each commit.
  - `v0.1.0` = `5feef11` "Initial public release v0.1.0" (changelog `[0.1.0]`, `__version__` 0.1.0)
  - `v0.1.1` = `042d779` "Release v0.1.1: relay-bank-16 and MCP23017 fix" (changelog `[0.1.1]`; `__version__` was not bumped and still reads 0.1.0)
  - `v0.1.2` = `e88174d` "Release v0.1.2 changelog" (changelog `[0.1.2]`; `__version__` 0.1.0)
  - `v0.1.3` = `5aef1e9` "Release v0.1.3: public docs polish and portable install paths" (changelog `[0.1.3]`; `__version__` 0.1.0)
  - `v0.2.0` = `8998f0b` "Add unified mqttpi daemon (GPIO + BMS) v0.2.0" (changelog `[0.2.0]`, `__version__` 0.2.0)
- **Step 4 (create and push tags) is a human step.** Not done; agents must not create tags. Commands for the owner, after approval:
  `for t in "v0.1.0 5feef11" "v0.1.1 042d779" "v0.1.2 e88174d" "v0.1.3 5aef1e9" "v0.2.0 8998f0b"; do set -- $t; git tag -a $1 $2 -m "mqttpi ${1#v}"; done && git push origin --tags`
