#!/usr/bin/env python3
"""JBD BMS UART → MQTT bridge (mqttpi)."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict

from mqttpi.bms.ha_mqtt import BmsMqttPublisher
from mqttpi.bms.jbd_uart import JbdUartClient
from mqttpi.config import load_config

log = logging.getLogger("mqttpi.bms")


def device_id_from_port(port: str) -> str:
    slug = port.rsplit("/", 1)[-1].lower().replace("-", "_")
    return f"jbd_{slug}"


def build_publisher(cfg: Dict[str, Any]) -> BmsMqttPublisher:
    mqtt_cfg = cfg.get("mqtt", {})
    bms_cfg = cfg.get("bms", {})
    device_cfg = cfg.get("device", {})
    ha_cfg = bms_cfg.get("ha", {})

    port = bms_cfg.get("port", "/dev/serial0")
    device_id = device_cfg.get("id", "bms-node")
    ha_name = ha_cfg.get("name") or device_cfg.get("ha", {}).get("name") or "LiFePO4 Battery"

    return BmsMqttPublisher(
        host=mqtt_cfg.get("host", "localhost"),
        port=int(mqtt_cfg.get("port", 1883)),
        username=mqtt_cfg.get("username", ""),
        password=mqtt_cfg.get("password", ""),
        base_topic=mqtt_cfg.get("base_topic", f"mqttpi/{device_id}"),
        client_id=mqtt_cfg.get("client_id", f"mqttpi-{device_id}"),
        device_name=ha_name,
        device_id=ha_cfg.get("device_id") or device_id_from_port(port),
        discovery_prefix=mqtt_cfg.get("homeassistant", {}).get(
            "discovery_prefix", "homeassistant"
        ),
        retain=bool(mqtt_cfg.get("retain", True)),
    )


def poll_once(cfg: Dict[str, Any], mqtt_pub: BmsMqttPublisher) -> bool:
    bms_cfg = cfg.get("bms", {})
    port = bms_cfg.get("port", "").strip()
    if not port:
        raise ValueError("bms.port is required (e.g. /dev/serial0 or /dev/ttyUSB0)")

    client = JbdUartClient(
        port=port,
        baudrate=int(bms_cfg.get("baudrate", 9600)),
        response_timeout=float(bms_cfg.get("response_timeout", 2)),
    )

    try:
        client.open()
        data = client.read_all()
        mqtt_pub.publish(data, port)
        log.info(
            "Published: %.2fV %.2fA SOC=%d%% cells=%d temps=%s",
            data.total_voltage,
            data.current,
            data.soc,
            len(data.cell_voltages),
            [round(t, 1) for t in data.temperatures_c],
        )
        return True
    finally:
        client.close()


def run_bridge(cfg: Dict[str, Any]) -> None:
    bms_cfg = cfg.get("bms", {})
    mqtt_pub = build_publisher(cfg)
    mqtt_pub.connect()

    poll_interval = float(bms_cfg.get("poll_interval", 30))
    retry_delay = float(bms_cfg.get("retry_delay", 10))
    stop = False

    def _stop(*_args: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log.info(
        "BMS bridge started (poll %ss, port %s)",
        poll_interval,
        bms_cfg.get("port"),
    )

    try:
        while not stop:
            try:
                poll_once(cfg, mqtt_pub)
                deadline = time.monotonic() + poll_interval
                while not stop and time.monotonic() < deadline:
                    time.sleep(0.5)
            except Exception as exc:
                log.exception("Poll failed: %s", exc)
                mqtt_pub.publish_offline()
                deadline = time.monotonic() + retry_delay
                while not stop and time.monotonic() < deadline:
                    time.sleep(0.5)
    finally:
        mqtt_pub.publish_offline()
        mqtt_pub.disconnect()
        log.info("BMS bridge stopped")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mqttpi JBD BMS UART → MQTT bridge")
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "-s",
        "--secrets",
        type=Path,
        default=Path("secrets.yaml"),
        help="Path to secrets.yaml (optional)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if not args.config.exists():
        log.error("Config not found: %s", args.config)
        return 1

    cfg = load_config(args.config, args.secrets if args.secrets.exists() else None)
    if not cfg.get("bms", {}).get("enabled", True):
        log.error("bms.enabled is false — nothing to do")
        return 1

    if args.once:
        mqtt_pub = build_publisher(cfg)
        mqtt_pub.connect()
        try:
            poll_once(cfg, mqtt_pub)
        finally:
            mqtt_pub.disconnect()
        return 0

    run_bridge(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())