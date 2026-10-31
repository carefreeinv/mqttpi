# mqttpi — starter config

**Config file:** [`config.example.yaml`](config.example.yaml)

---

## Purpose

Minimal empty template for a new mqttpi node. All peripherals are **disabled** (`profile: maximum_gpio`) so every legal GPIO pin stays in the MQTT pool until you add `pins[]` entries or enable buses.

Copy this when you are building a custom layout from scratch rather than starting from a named example.

---

## Quick start

```bash
cp config.example.yaml config.yaml
cp secrets.example.yaml secrets.yaml
# edit device.id, mqtt.host, secrets.yaml
```

For ready-made layouts, prefer [`examples/README.md`](examples/README.md) — each YAML has a matching `.md` with wiring, FAQ, and design notes.

---

## What you must change

| Field | Why |
|-------|-----|
| `device.id` | Unique per board on the broker |
| `mqtt.host` | Your MQTT broker IP/hostname |
| `secrets.yaml` → `mqtt.username` / `password` | Broker credentials |
| `device.ha.name` | Home Assistant device registry label |
| `pins[]` | Your actual wiring |

---

## Defaults (design decisions)

| Decision | Choice |
|----------|--------|
| Default board | **Pico W** |
| Default profile | **`maximum_gpio`** — all buses/PWM off |
| HA integration | Discovery **on**, payloads **ON/OFF**, state **retained** |
| Secrets | **`secrets.yaml`** merged at runtime (gitignored) |
| Topic root | `mqttpi/{device.id}` unless overridden |
| Availability | `{base_topic}/status` retained `online`/`offline`; MQTT Last Will marks a crashed node `offline` |
| `mqtt.keepalive` | `60` s — broker declares a silent node dead after ~1.5× this |
| `mqtt.tls` | `false` (plain TCP). `true` = TLS verified against the system CA store. Mapping: `ca_certs`, `certfile` + `keyfile` (client certificate), `insecure: true` (skip hostname check — lab only, logged as a warning). Missing files or unknown keys are startup errors. See [daemon.md](daemon.md#tls) |
| `mqtt.port` | `1883`, or `8883` when TLS is on and no port is set |
| `gpio.backend` | `rpi` (default) or `mock` — mock never touches hardware; with `rpi`, a missing GPIO library is a startup error |
| `mqtt.reconnect_min_s` / `mqtt.reconnect_max_s` | `1` / `60` s — background connect/reconnect backoff; the daemon starts even when the broker is down |
| `mqtt.max_queued_messages` | `1000` — qos>0 messages buffered while disconnected (newest dropped when full; `0` = unbounded) |
| `mqtt.homeassistant.discovery_node_id` | `false` — discovery on `homeassistant/<component>/<device.id>_<alias>/config` (unchanged). `true` (use `device.id`) or a string node id: `homeassistant/<component>/<node_id>/<alias>/config`, for per-node broker ACLs. `discovery_clear_legacy` (default `true`) empties the old-layout configs first. See [daemon.md](daemon.md#discovery-topics-and-per-node-acls) |
| `sensors` | Absent. Numeric sensor entities: `sensors.<name>.type` (e.g. `cpu_temperature`), `publish.interval_ms` (default `30000`), `timeout_s`, `stale_after_s`, `readings.<key>.{alias, precision, ha}`; state on `{base_topic}/sensors/<alias>/state`. See [daemon.md](daemon.md#sensors-numeric-readings) |

---

## GPIO pool (Pico W, all peripherals off)

23 pins: GP0–6, GP7–22, GP26–28 (minus platform GP23–25).

Enable a bus or PWM in config to **reserve** pins — see any example doc for pin budget tables.

---

## FAQ

**Q: Should I edit `config.example.yaml` directly?**  
A: No. Copy to `config.yaml` (gitignored) and edit that.

**Q: Where do MQTT passwords go?**  
A: `secrets.yaml` only — never commit credentials.

**Q: How do entities appear in Home Assistant?**  
A: Enable MQTT integration with discovery; run `python3 -m mqttpi` — the daemon publishes `homeassistant/*/config` on startup.

**Q: Is this file enough to run mqttpi today?**  
A: Add `pins[]` entries (see [`relay-bank-16.yaml`](examples/relay-bank-16.yaml)) or enable `bms` (see [`jbd-bms.yaml`](examples/jbd-bms.yaml)), then start the [daemon](daemon.md). An empty `pins[]` with no `bms.enabled` has nothing to run.

---

## Related

- [daemon.md](daemon.md) — unified daemon quick start and systemd notes
- [examples/README.md](examples/README.md) — full example index
- [examples/relay-bank-16.md](examples/relay-bank-16.md) — 16 relay GPIO example (supported)
- [examples/jbd-bms.md](examples/jbd-bms.md) — JBD BMS example (supported)