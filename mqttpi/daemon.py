"""Unified mqttpi daemon — GPIO relays/sensors and optional BMS."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mqttpi.bms.subsystem import BmsSubsystem, bms_enabled
from mqttpi.config import load_config
from mqttpi.gpio.manager import GpioManager
from mqttpi.gpio.pins import parse_pins
from mqttpi.mqtt.client import MqttConnection

log = logging.getLogger("mqttpi")


def build_mqtt(cfg: Dict[str, Any]) -> MqttConnection:
    mqtt_cfg = cfg.get("mqtt", {})
    device_cfg = cfg.get("device", {})
    device_id = str(device_cfg.get("id", "mqttpi-node"))
    return MqttConnection(
        host=str(mqtt_cfg.get("host", "localhost")),
        port=int(mqtt_cfg.get("port", 1883)),
        username=str(mqtt_cfg.get("username", "")),
        password=str(mqtt_cfg.get("password", "")),
        client_id=str(mqtt_cfg.get("client_id", f"mqttpi-{device_id}")),
        retain=bool(mqtt_cfg.get("retain", True)),
        qos=int(mqtt_cfg.get("qos", 1)),
    )


def enabled_subsystems(cfg: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    if parse_pins(cfg):
        names.append("gpio")
    if bms_enabled(cfg):
        names.append("bms")
    return names


class Daemon:
    def __init__(
        self,
        cfg: Dict[str, Any],
        mock_gpio: bool = False,
    ) -> None:
        self.cfg = cfg
        self.mock_gpio = mock_gpio
        self._stop = False
        self._mqtt: Optional[MqttConnection] = None
        self._gpio: Optional[GpioManager] = None
        self._bms: Optional[BmsSubsystem] = None

    def run(self) -> None:
        subsystems = enabled_subsystems(self.cfg)
        if not subsystems:
            raise RuntimeError(
                "No enabled subsystems — add pins[] and/or bms.enabled: true to config"
            )

        log.info("Starting mqttpi daemon (%s)", ", ".join(subsystems))

        self._mqtt = build_mqtt(self.cfg)
        handlers = []

        if "gpio" in subsystems:
            self._gpio = GpioManager(self.cfg, self._mqtt, mock_gpio=self.mock_gpio)
            handlers.append(self._gpio.handle_mqtt_message)

        if "bms" in subsystems:
            self._bms = BmsSubsystem(self.cfg)

        def on_message(topic: str, payload: str) -> None:
            for handler in handlers:
                handler(topic, payload)

        self._mqtt.set_message_handler(on_message)
        self._mqtt.connect()

        mqtt_cfg = self.cfg.get("mqtt", {})
        base_topic = str(mqtt_cfg.get("base_topic", "mqttpi"))
        self._mqtt.publish_availability(base_topic, True)

        if self._gpio is not None:
            self._gpio.start()
        if self._bms is not None:
            self._bms.start()

        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

        while not self._stop:
            signal.pause()

        self.shutdown()

    def shutdown(self) -> None:
        if self._bms is not None:
            self._bms.stop()
        if self._gpio is not None:
            self._gpio.stop()
        if self._mqtt is not None:
            mqtt_cfg = self.cfg.get("mqtt", {})
            base_topic = str(mqtt_cfg.get("base_topic", "mqttpi"))
            self._mqtt.publish_availability(base_topic, False)
            self._mqtt.disconnect()
        log.info("mqttpi daemon stopped")

    def _handle_stop(self, *_args: object) -> None:
        self._stop = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="mqttpi unified daemon (GPIO + optional BMS)"
    )
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
    parser.add_argument(
        "--mock-gpio",
        action="store_true",
        help="Use in-memory GPIO backend (no hardware)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if not args.config.exists():
        log.error("Config not found: %s", args.config)
        return 1

    cfg = load_config(args.config, args.secrets if args.secrets.exists() else None)

    try:
        Daemon(cfg, mock_gpio=args.mock_gpio).run()
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())