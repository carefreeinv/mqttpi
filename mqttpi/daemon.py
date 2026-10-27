"""Unified mqttpi daemon — GPIO relays/sensors and optional BMS."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from mqttpi.bms.subsystem import BmsSubsystem, bms_enabled
from mqttpi.config import load_config
from mqttpi.gpio.commands import CommandFilter
from mqttpi.gpio.manager import GpioManager
from mqttpi.gpio.pins import parse_pins
from mqttpi.mqtt.client import MqttConnection
from mqttpi.mqtt.factory import base_topic_from, build_mqtt  # noqa: F401 (re-exported)
from mqttpi.sensors.config import sensors_configured
from mqttpi.sensors.subsystem import SensorSubsystem

log = logging.getLogger("mqttpi")


def enabled_subsystems(cfg: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    if parse_pins(cfg):
        names.append("gpio")
    if bms_enabled(cfg):
        names.append("bms")
    if sensors_configured(cfg):
        names.append("sensors")
    return names


class Daemon:
    def __init__(
        self,
        cfg: Dict[str, Any],
        mock_gpio: bool = False,
        command_filters: Optional[Sequence[CommandFilter]] = None,
    ) -> None:
        """``command_filters`` are registered on the GPIO manager before it
        starts, so they apply to the very first MQTT command (see
        ``mqttpi.gpio.commands``)."""
        self.cfg = cfg
        self.mock_gpio = mock_gpio
        self.command_filters: List[CommandFilter] = list(command_filters or [])
        self._stop = threading.Event()
        self._mqtt: Optional[MqttConnection] = None
        self._gpio: Optional[GpioManager] = None
        self._bms: Optional[BmsSubsystem] = None
        self._sensors: Optional[SensorSubsystem] = None

    def run(self) -> None:
        subsystems = enabled_subsystems(self.cfg)
        if not subsystems:
            raise RuntimeError(
                "No enabled subsystems — add pins[], sensors, and/or bms.enabled: true to config"
            )

        log.info("Starting mqttpi daemon (%s)", ", ".join(subsystems))

        self._mqtt = build_mqtt(self.cfg)
        handlers = []

        if "gpio" in subsystems:
            self._gpio = GpioManager(self.cfg, self._mqtt, mock_gpio=self.mock_gpio)
            for command_filter in self.command_filters:
                self._gpio.add_command_filter(command_filter)
            handlers.append(self._gpio.handle_mqtt_message)

        if "bms" in subsystems:
            self._bms = BmsSubsystem(self.cfg, connection=self._mqtt)

        if "sensors" in subsystems:
            self._sensors = SensorSubsystem(self.cfg, connection=self._mqtt)

        def on_message(topic: str, payload: str) -> None:
            for handler in handlers:
                handler(topic, payload)

        self._mqtt.set_message_handler(on_message)
        # Non-blocking: subsystems start even when the broker is down.
        # Availability "online", subscriptions, and HA discovery are
        # (re)published on every successful connect; the Last Will covers
        # abrupt exits.
        self._mqtt.connect()

        if self._gpio is not None:
            self._gpio.start()
        if self._bms is not None:
            self._bms.start()
        if self._sensors is not None:
            self._sensors.start()

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, self._handle_stop)
            signal.signal(signal.SIGTERM, self._handle_stop)

        while not self._stop.wait(1.0):
            pass

        self.shutdown()

    @property
    def gpio(self) -> Optional[GpioManager]:
        """The running GPIO manager (``None`` before ``run()`` or without pins)."""
        return self._gpio

    @property
    def sensors(self) -> Optional[SensorSubsystem]:
        """The running sensor subsystem (``None`` before ``run()`` or without sensors)."""
        return self._sensors

    def stop(self) -> None:
        """Ask ``run()`` to shut down (thread-safe; for embedding applications)."""
        self._stop.set()

    def shutdown(self) -> None:
        if self._sensors is not None:
            self._sensors.stop()
        if self._bms is not None:
            self._bms.stop()
        if self._gpio is not None:
            self._gpio.stop()
        if self._mqtt is not None:
            self._mqtt.publish_availability(online=False)
            self._mqtt.disconnect()
        log.info("mqttpi daemon stopped")

    def _handle_stop(self, *_args: object) -> None:
        self._stop.set()


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
    except (RuntimeError, ValueError) as exc:
        log.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())