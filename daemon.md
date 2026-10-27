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

## Startup and reconnect

The daemon does **not** need the broker to be up when it starts:

- GPIO outputs are set to their `initial` values, inputs are polled, and BMS polling runs immediately, whether or not MQTT is connected.
- The MQTT connection is made in the background and retried with exponential backoff between `mqtt.reconnect_min_s` (default `1`) and `mqtt.reconnect_max_s` (default `60`) seconds — at startup and after any later outage.
- On every successful (re)connect the daemon re-subscribes to its `…/set` topics and re-publishes availability (`online`), Home Assistant discovery, and the current state of every pin, so a broker restarted without persistence is fully repopulated.
- While disconnected, qos 1/2 messages (the default `mqtt.qos: 1`) are queued in memory up to `mqtt.max_queued_messages` (default `1000`; `0` = unbounded). Once the queue is full, **new** messages are dropped. qos 0 messages are dropped while disconnected. State is re-published on reconnect anyway, so dropped intermediate states are not lost for long.
- The log shows one warning per outage (plus one reminder after 10 failed attempts to check `mqtt.host` / `mqtt.port`), not one per retry.
- Configuration errors (empty or malformed `mqtt.host`, out-of-range `mqtt.port`, inconsistent backoff bounds) still fail fast with exit code 1.

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

**BMS poll failures** — See [jbd-bms.md](examples/jbd-bms.md) wiring FAQ. The standalone bridge (`--once -v`) is the fastest UART diagnostic.