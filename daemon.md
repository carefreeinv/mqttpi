# mqttpi daemon

The **unified mqttpi daemon** reads `config.yaml` (+ `secrets.yaml`) and starts whichever subsystems the config enables:

| Config section | Subsystem | Status |
|----------------|-----------|--------|
| `pins[]` with `direction: output` or `input` | GPIO → MQTT → Home Assistant | **Implemented** (v0.2) |
| `bms.enabled: true` | JBD UART → MQTT → HA | **Implemented** |

Other example configs (PWM, CAN, I2C expanders, Victron, …) remain **config contracts** until their drivers are added.

## Supported examples today

| Example | Command |
|---------|---------|
| [`relay-bank-16.yaml`](examples/relay-bank-16.yaml) | 16 relay outputs on native GPIO |
| [`jbd-bms.yaml`](examples/jbd-bms.yaml) | JBD BMS UART monitor (Pi) |
| Combined | Both sections in one `config.yaml` |

## Quick start

```bash
pip3 install -r requirements.txt
cp examples/relay-bank-16.yaml config.yaml   # or jbd-bms.yaml
cp secrets.example.yaml secrets.yaml
# Edit mqtt.host, device.id, secrets.yaml

# Foreground (recommended while testing)
python3 -m mqttpi -v

# GPIO without hardware (mock backend)
python3 -m mqttpi -c examples/relay-bank-16.yaml --mock-gpio -v
```

The daemon stays in the foreground until you press Ctrl+C. It publishes `{base_topic}/status` as `online` while running and `offline` on exit.

## What the daemon does

```mermaid
flowchart TD
    start([Start daemon]) --> load["Load config.yaml + secrets.yaml"]
    load --> mqtt["Connect MQTT broker<br/>(one client per process)"]
    mqtt --> gpio{pins[] non-empty?}
    gpio -->|yes| gpio_run["GPIO subsystem<br/>Configure outputs/inputs<br/>Publish HA discovery<br/>Subscribe gpio/set topics<br/>Poll inputs with debounce"]
    gpio -->|no| bms
    gpio_run --> bms{bms.enabled?}
    bms -->|yes| bms_run["BMS subsystem<br/>Poll JBD UART<br/>Publish sensor state + discovery"]
    bms -->|no| loop([Run until exit])
    bms_run --> loop
    loop --> status["Publish status online/offline"]
```

## GPIO backend

On a Pi the daemon drives pins through `RPi.GPIO` (installed from `requirements.txt` on ARM Linux only). If the library is missing or cannot initialise, the daemon **exits with code 1** and an error naming the fix — it no longer silently falls back to a mock backend that only pretends to switch outputs.

The mock backend runs only when asked for:

- `--mock-gpio` on the command line, or
- `gpio: {backend: mock}` in `config.yaml` (`backend` is `rpi` by default).

The startup log shows the active backend and board, e.g. `GPIO backend: rpi (board: rpi4)`; library users can read `GpioManager.backend_name`.

**Raspberry Pi 5 / newer kernels:** `RPi.GPIO` cannot drive the Pi 5 GPIO chip. Install the drop-in replacement `rpi-lgpio` (provides the same `RPi.GPIO` module): `pip uninstall -y RPi.GPIO && pip install rpi-lgpio`.

## Startup and reconnect

The daemon does **not** need the broker to be up when it starts:

- GPIO outputs are set to their `initial` values, inputs are polled, and BMS polling runs immediately, whether or not MQTT is connected.
- The MQTT connection is made in the background and retried with exponential backoff between `mqtt.reconnect_min_s` (default `1`) and `mqtt.reconnect_max_s` (default `60`) seconds — at startup and after any later outage.
- On every successful (re)connect the daemon re-subscribes to its `…/set` topics and re-publishes availability (`online`), Home Assistant discovery, and the current state of every pin, so a broker restarted without persistence is fully repopulated.
- While disconnected, qos 1/2 messages (the default `mqtt.qos: 1`) are queued in memory up to `mqtt.max_queued_messages` (default `1000`; `0` = unbounded). Once the queue is full, **new** messages are dropped. qos 0 messages are dropped while disconnected. State is re-published on reconnect anyway, so dropped intermediate states are not lost for long.
- The log shows one warning per outage (plus one reminder after 10 failed attempts to check `mqtt.host` / `mqtt.port`), not one per retry.
- Configuration errors (empty or malformed `mqtt.host`, out-of-range `mqtt.port`, inconsistent backoff bounds) still fail fast with exit code 1.

## TLS

`mqtt.tls` encrypts the broker connection. The certificate chain is always verified.

```yaml
mqtt:
  host: broker.example.lan
  tls: true                 # system CA store; port defaults to 8883
```

```yaml
mqtt:
  host: broker.example.lan
  port: 8883
  tls:
    ca_certs: /etc/mqttpi/ca.crt       # private CA
    certfile: /etc/mqttpi/client.crt   # optional client certificate
    keyfile: /etc/mqttpi/client.key
    # insecure: true                   # skip hostname check (lab only; warns)
```

- File paths can live in `secrets.yaml` (it is deep-merged onto `config.yaml`). Paths are checked at startup; missing or unreadable PEM files fail fast with exit code 1. Key material is never logged.
- The startup log names the transport, e.g. `MQTT connecting to broker.example.lan:8883 over TLS (CA /etc/mqttpi/ca.crt) …`.
- A failed handshake is logged once per outage as `TLS handshake failed (…CERTIFICATE_VERIFY_FAILED…) — check mqtt.tls.ca_certs, the broker certificate (expiry, hostname), and the system clock`, and the daemon keeps retrying (see [Startup and reconnect](#startup-and-reconnect)).
- **No RTC?** Boards without a real-time clock boot with a wrong date until NTP syncs, so certificates look not-yet-valid. The background retries recover once time syncs. Renew broker certificates before they expire on unattended nodes.

Minimal Mosquitto listener with a private CA:

```conf
# /etc/mosquitto/conf.d/tls.conf
listener 8883
cafile   /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile  /etc/mosquitto/certs/server.key
# require_certificate true   # enforce client certificates
```

The server certificate's subject alternative names must include the hostname or IP used in `mqtt.host`.

## Availability and Last Will

`{base_topic}/status` is the node's availability topic (retained):

| Event | Published by | Payload |
|-------|--------------|---------|
| Every successful connect or reconnect | daemon | `online` |
| Clean stop (Ctrl+C, `SIGTERM`, `systemctl stop`) | daemon | `offline` |
| Crash, `kill -9`, power loss, network drop | **broker** (MQTT Last Will) | `offline` |

The daemon registers the Last Will before connecting, so a node that disappears without a clean disconnect is marked `offline` by the broker once it notices the connection is gone (immediately when the TCP connection closes; otherwise after about 1.5 × `mqtt.keepalive` seconds, default 60). Lower `mqtt.keepalive` for faster detection of silent network drops.

Home Assistant discovery payloads for GPIO entities include `availability_topic`, so switches and binary sensors show as *unavailable* while the node is offline.

Library users get the same behavior from `MqttConnection(..., base_topic="mqttpi/node1")` (or `availability_topic=...`). Pass `will=False` to opt out; `payload_available` / `payload_not_available` override `online` / `offline`. Use `add_connect_callback()` to run code (re-subscribe, re-publish) after every reconnect.

## Command filters

Applications that embed mqttpi can inspect every output command **before** any pin changes, and accept, modify, or reject it. This keeps local interlocks and safety limits in charge while mqttpi still handles MQTT, discovery, and GPIO. With no filter registered, behavior is unchanged.

```python
from mqttpi.config import load_config
from mqttpi.daemon import Daemon
from mqttpi.gpio.commands import CommandDecision, block_while, mutually_exclusive

def no_heater_at_night(req):
    if req.alias == "heater" and req.value and req.states.get("night_mode"):
        return CommandDecision.reject("night mode")
    return None  # accept

cfg = load_config("config.yaml")
Daemon(cfg, command_filters=[
    mutually_exclusive("actuator_extend", "actuator_retract"),
    block_while("actuator_extend", "limit_extended"),
    no_heater_at_night,
]).run()
```

- A filter is any callable `filter(request) -> CommandDecision | None`. `CommandRequest` (frozen) carries `alias`, requested `value`, `current` value, `source` (the MQTT topic, or `"api"`), raw `payload`, and a read-only `states` snapshot of every output and input.
- Return `None` / `CommandDecision.accept()`, `CommandDecision.modify(value, reason)`, or `CommandDecision.reject(reason)`.
- Filters run in registration order; a modify is passed on to later filters; the **first reject wins**. A filter that raises counts as a reject and is logged (fail safe).
- After a reject or modify the **actual** output state is re-published, so Home Assistant never shows a state the hardware is not in. Rejections are logged at INFO with the reason.
- Filters run on the MQTT network thread: keep them fast and non-blocking (no I/O, no sleeps). A filter slower than 50 ms logs a warning.
- Built-ins: `mutually_exclusive(*aliases)` (at most one ON — e.g. the two direction relays of a reversible motor) and `block_while(alias, input_alias, active=True)` (refuse ON while an input is active; OFF is always allowed).
- Without the stock daemon: `GpioManager.add_command_filter(f)`; `GpioManager.request_output(alias, on)` sets an output from code through the same filters.

Filters are library-only for now (no config syntax). See [linear-actuator.md](examples/linear-actuator.md) for a runnable example.

## Standalone BMS bridge

`python3 -m mqttpi.bms.bridge` still works for BMS-only deployments and one-shot tests (`--once`). New installs should prefer `python3 -m mqttpi` so GPIO and BMS can share one process when needed.

## Board notes

| `device.board` | GPIO runtime |
|----------------|--------------|
| `pi4`, `pi5` | RPi.GPIO (BCM pin numbers from `pins[].pin`) |
| `picow` | Same Linux daemon for bring-up; production Pico W nodes will use a future MicroPython firmware port |

The [`relay-bank-16`](examples/relay-bank-16.md) example targets Pico W pin numbering (GP0–GP15). On a Raspberry Pi, use BCM pins that match your wiring or adapt the config.

## systemd (optional — not installed by default)

A unit template ships at [`mqttpi.service`](mqttpi.service). **Nothing is installed automatically.** When you are ready for a persistent service:

```bash
sudo cp mqttpi.service /etc/systemd/system/
# Edit paths in the unit if the repo is not at ~/mqttpi
sudo systemctl enable --now mqttpi.service
```

`mqttpi-bms.service` remains available for BMS-only setups that still use the standalone bridge.

## Troubleshooting

**No entities in Home Assistant** — Confirm MQTT credentials, that HA discovery is enabled, and that the daemon log shows `Published HA discovery`.

**`No enabled subsystems`** — Add `pins[]` entries and/or `bms.enabled: true`.

**GPIO permission errors** — Run as a user in the `gpio` group, or use `--mock-gpio` to verify MQTT wiring without hardware.

**`GPIO backend 'rpi' unavailable`** — The GPIO library is not installed or cannot open the GPIO chip. Run `pip install -r requirements.txt` on the Pi (or `sudo apt install python3-rpi.gpio` and create the venv with `--system-site-packages`); on a Pi 5 install `rpi-lgpio`. To test without hardware use `--mock-gpio` or `gpio: {backend: mock}`.

**BMS poll failures** — See [jbd-bms.md](examples/jbd-bms.md) wiring FAQ. The standalone bridge (`--once -v`) is the fastest UART diagnostic.