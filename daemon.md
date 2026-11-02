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
    bms -->|no| sensors{sensors with a driver?}
    bms_run --> sensors
    sensors -->|yes| sensors_run["Sensor subsystem<br/>Poll drivers on a schedule<br/>Publish sensor state + discovery"]
    sensors -->|no| loop([Run until exit])
    sensors_run --> loop
    loop --> status["Publish status online/offline"]
```

## Sensors (numeric readings)

A `sensors` section turns readings from drivers (1-Wire, I2C, ADC, CAN-derived values, …) into Home Assistant `sensor` entities on the same HA device as the GPIO entities. The subsystem starts when at least one enabled sensor has a driver. A sensor whose `type` has no driver yet is skipped with a warning, so configs written for future drivers (`mpu6050`, `vl53l0x`, … in `examples/`) still load.

Built-in driver today: `cpu_temperature` (SoC temperature from `/sys/class/thermal/thermal_zone0/temp`; `path:` overrides it). Hardware drivers plug in through `mqttpi.sensors.register_driver`.

```yaml
sensors:
  cpu:
    type: cpu_temperature          # aliases: chip, driver
    publish: { interval_ms: 30000, retain: true }
    # timeout_s: 10                # default: min(interval, 10 s)
    # stale_after_s: 90            # default: 3 × interval, at least 10 s
    # readings:                    # optional; the driver supplies defaults
    #   temperature:
    #     alias: cpu_temperature   # default: <sensor>_<key>
    #     precision: 1
    #     ha: { name: "CPU Temperature", device_class: temperature,
    #           state_class: measurement, unit_of_measurement: "°C" }
```

The list form (`sensors: [{name: cpu, type: cpu_temperature}]`) is accepted too. Extra keys under `ha:` (for example `expire_after`) are passed through to discovery.

| Topic (under `{base_topic}`) | Payload |
|------------------------------|---------|
| `sensors/<alias>/state` | The number, e.g. `48.3` (rounded to `precision` when set) |
| `sensors/<alias>/attributes` | JSON `{"timestamp": "2026-01-01T12:00:00+00:00", "quality": "good"}` (`good` or `uncertain`) |
| `sensors/<alias>/availability` | `online` / `offline`, retained |

Discovery: `homeassistant/sensor/<device.id>_<alias>/config` (or the node-id layout), with `unit_of_measurement`, `device_class`, `state_class`, `suggested_display_precision`, `json_attributes_topic`, and `availability` = [node status, entity availability] with `availability_mode: all`.

**Polling:** one scheduler thread polls every sensor at its own interval. Reads run in worker threads, so a slow driver only delays itself. A read still running after `timeout_s` counts as a failure, its late result is discarded, and that sensor is not polled again until the read returns. A failed read (exception, timeout, `bad` quality, or no numeric value) publishes nothing. When a sensor has had no good reading for `stale_after_s`, its entities go `offline`. The next good reading brings them back `online`. Entities start `offline` until their first good reading.

**Writing a driver:** implement `read() -> mqttpi.sensors.Reading` (values keyed by reading name, plus optional `quality`) and register a factory: `register_driver("mychip", lambda spec: MyChip(spec["address"]))`. Optional `default_readings` supplies units and classes, and optional `close()` runs on shutdown. Tests can use a fake driver in the same way; see `tests/test_sensors.py`.

## Sensor drivers

| `type` | Readings (defaults) | Bus / setup |
|--------|---------------------|-------------|
| `cpu_temperature` | `temperature` °C | Linux thermal sysfs (no setup) |
| `ds18b20` | `temperature` °C (0.01) | 1-Wire through the kernel `w1` sysfs. Add `dtoverlay=w1-gpio,gpiopin=4` to `/boot/firmware/config.txt` and a 4.7 kΩ pull-up to 3.3 V. `address: 28-…` (from `ls /sys/bus/w1/devices/`) is optional with a single probe |
| `bme280` / `bmp280` | `temperature` °C, `humidity` % (BME280 only), `pressure` hPa | I2C, `address` 0x76 (default) or 0x77, forced mode with ×1 oversampling |
| `sht3x` (`sht30`/`sht31`/`sht35`) | `temperature` °C, `humidity` % | I2C, `address` 0x44 (default) or 0x45, single shot with a CRC check |
| `sht4x` (`sht40`/`sht41`/`sht45`) | `temperature` °C, `humidity` % | I2C, `address` 0x44, high precision with a CRC check |

- **I2C setup:**
  - Enable the bus with `sudo raspi-config` → Interface Options → I2C (or `dtparam=i2c_arm=on`).
  - Install `smbus2` (`pip install smbus2`, or the `mqttpi[i2c]` extra).
  - Find addresses with `i2cdetect -y 1`. `bus:` selects `/dev/i2c-N` (default 1).
  - Sensors on one bus share a single handle and a lock.
- **Failure handling:** buses are opened on the first read, not while the config loads. A missing `smbus2`, an absent `/dev/i2c-1`, a NACK, a CRC error or an unplugged probe each count as a failed read. The sensor goes `offline` once `stale_after_s` passes, and relays, PWM and the BMS keep running.
- **DS18B20 power-on value:** an 85.000 °C reading (the power-on value) is published with quality `uncertain`. Out-of-range values (for example −127 °C from a bad contact) are treated as failed reads.
- **Bus lockups:** if an I2C device holds SDA low after a brown-out, reads fail until it is power-cycled. Power I2C sensors from a switchable rail on unattended nodes.
- **Documented ahead of drivers** (configs load, and the entries are skipped with a warning):
  - `analog_input` pins with `source: ads1115` (an external ADC, [analog-inputs.yaml](examples/analog-inputs.yaml));
  - `ina219` / `ina226` power monitors ([power-monitor.md](examples/power-monitor.md)).

## PWM outputs

A pin with `direction: pwm_output` becomes a Home Assistant `number` entity. Its state is on `{base_topic}/gpio/<alias>/state` and commands go to `{base_topic}/gpio/<alias>/set`. The payload is the duty in percent (`0`–`100`, decimals allowed), or `ON` (= `ha.max`) / `OFF` (= 0).

```yaml
pins:
  - pin: 18
    alias: fan
    direction: pwm_output
    frequency_hz: 1000        # default 1000
    initial_duty: 0           # default 0 (safe start)
    # invert: true            # active-low driver: logical 100 % = pin LOW
    # pwm_mode: hardware      # default software; see below
    # pwm_chip: 0             # hardware: /sys/class/pwm/pwmchip<N> (Pi 5: usually 2 — check ls /sys/class/pwm)
    # pwm_channel: 0          # hardware: override the pin → channel map
    ha: { name: "Fan", min: 0, max: 100, step: 1, unit_of_measurement: "%", icon: "mdi:fan" }
```

- **Clamping:** values above `ha.max` are clamped to `ha.max`. Values between 0 and `ha.min` go up to `ha.min`, which suits a motor's minimum speed. `0` (off) is always allowed.
- **Command filters** see PWM commands too. `CommandRequest.value` and `current` are the duty as a float, and `states()` includes duties. `mutually_exclusive(...)` and `block_while(...)` treat any duty above 0 as ON. `clamp_duty(alias, low, high)` caps a channel.
- **Shutdown:** every PWM output goes to 0 % before GPIO cleanup.
- **Software PWM** (`pwm_mode: software`, the default) uses `RPi.GPIO.PWM`, or rpi-lgpio on a Pi 5. It works on any pin, but it is timed by a thread, so expect jitter. That is fine for LEDs, fans and DC motor speed, and not for servos. Above 1 kHz a warning is logged.
- **Hardware PWM** (`pwm_mode: hardware`) writes to the kernel PWM sysfs (`/sys/class/pwm/pwmchip<N>`). It is accurate up to tens of kHz, but only on GPIO 12, 13, 18 and 19.
  - Channel map: on a Pi Zero/3/4, 12/18 → channel 0 and 13/19 → channel 1; on a Pi 5, 12/13/18/19 → channels 0/1/2/3.
  - You must route the pins with an overlay in `/boot/firmware/config.txt`, for example `dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4`, then reboot.
  - It is opt-in because a channel routed to a different pin than the one configured would drive the wrong pin. Board validation rejects `pwm_mode: hardware` on other pins.

## GPIO inputs and debounce

Inputs are polled every 20 ms. A new reading is published once it has been stable for the pin's `debounce_ms` (default 50 ms). Contact bounce or a glitch shorter than that is ignored, and each bounce restarts the timer. Expect state changes in Home Assistant about `debounce_ms` after the physical edge. For limit switches and fast safety inputs, keep `debounce_ms` small (10–30 ms).

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

## Discovery topics and per-node ACLs

By default discovery configs go to `homeassistant/<component>/<device.id>_<alias>/config` (unchanged). Set `mqtt.homeassistant.discovery_node_id` to use Home Assistant's node-id form instead:

```yaml
mqtt:
  homeassistant:
    discovery: true
    discovery_node_id: true      # or an explicit id, e.g. "garage-2" (letters, digits, _ and -)
```

| Entity | Default topic | With `discovery_node_id: true` |
|--------|---------------|--------------------------------|
| GPIO switch `relay_1` on `node1` | `homeassistant/switch/node1_relay_1/config` | `homeassistant/switch/node1/relay_1/config` |
| BMS sensor `soc` (BMS id `jbd_x`) on `node1` | `homeassistant/sensor/jbd_x_soc/config` | `homeassistant/sensor/node1/jbd_x_soc/config` |

`unique_id` values do not change, so Home Assistant keeps entity ids and history.

Every discovery topic of a node now sits under `homeassistant/+/<node_id>/`, so the broker can confine each node to its own topics. A Mosquitto ACL example, with one MQTT user per node, named after the node id:

```text
# /etc/mosquitto/acl  (mosquitto.conf: acl_file /etc/mosquitto/acl)
pattern readwrite mqttpi/%u/#
pattern write homeassistant/+/%u/#

# Home Assistant's own user
user homeassistant
topic readwrite #
```

**Migrating an existing node:** when the node layout is on, mqttpi first publishes an empty retained payload to each entity's old flat-layout topic, then publishes the new config. This removes the old discovery entry before the new one appears, so Home Assistant never sees the same `unique_id` twice. The cleanup is a write outside the node's ACL scope, so either switch layouts **before** tightening the ACL, or clear the old topics as the admin user (`mosquitto_pub -r -n -t homeassistant/switch/node1_relay_1/config`). Set `discovery_clear_legacy: false` to skip the cleanup. Switching back to the flat layout does not clear the node-layout topics; remove those the same way.

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

## BMS and the MQTT connection

In the unified daemon the BMS subsystem **shares the daemon's single MQTT connection**: one client id (`mqtt.client_id`), one Last Will, one node availability topic (`{base_topic}/status`).

BMS health is reported separately on `{base_topic}/bms/status` (retained `online` after a successful poll, `offline` when a poll fails or the subsystem stops). BMS entities in Home Assistant use both topics with `availability_mode: all`, so:

- the node goes down (crash, power, network) → every entity is unavailable (Last Will);
- only the BMS link fails (UART unplugged) → BMS entities are unavailable, GPIO entities stay available.

Entity unique ids, state topics, and the other discovery fields are unchanged.

## Standalone BMS bridge

`python3 -m mqttpi.bms.bridge` (or `mqttpi-bms`) still works for BMS-only deployments and one-shot tests (`--once`). It opens its own connection, which now has the same Last Will and background reconnect as the daemon, and uses `{base_topic}/status` for BMS availability as before.

Its client id is `bms.client_id` if set, otherwise `{mqtt.client_id}-bms`, so it never collides with a daemon running on the same config. `--once` waits up to 10 s for the broker and exits with an error if it is unreachable.

New installs should prefer `python3 -m mqttpi` so GPIO and BMS share one process and one connection.

## Board notes

| `device.board` | GPIO (validated) | Hardware PWM | ADC | GPIO runtime / notes |
|----------------|------------------|--------------|-----|----------------------|
| `pi3`, `pi4` | BCM 0–27 | 12, 13, 18, 19 | none | RPi.GPIO (BCM pin numbers from `pins[].pin`) |
| `pi5` | BCM 0–27 | 12, 13, 18, 19 | none | Install `rpi-lgpio` (RPi.GPIO-compatible); classic RPi.GPIO does not support the Pi 5 |
| `pizero` (`pizero2w`, `pizero_w`, `zero2w`) | BCM 0–27 | 12, 13, 18, 19 | none | RPi.GPIO; Zero W is single-core ARMv6, Wi-Fi 2.4 GHz only — see [pizero-relays](examples/pizero-relays.md) |
| `picow` (`pico_w`) | GP0–22, 26–28 | all GPIO | GP26–28 | Same Linux daemon for bring-up; production Pico W nodes will use a future MicroPython firmware port |

At startup the GPIO manager checks `pins[]` against the board profile ([`mqttpi/boards.py`](mqttpi/boards.py)) and refuses to start, listing every problem, when a pin does not exist on the board, is used twice, or is claimed by an enabled bus (any pin setting under an enabled `buses.*` entry, or GPIO 14/15 when `bms.port` is `/dev/serial0`). It logs a warning for GPIO 0/1 (HAT ID EEPROM), `analog` pins without an ADC, and `pwm` pins without hardware PWM. A missing or unknown `device.board` skips validation (warning only), so existing configs keep working.

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