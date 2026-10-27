"""Shared MQTT helpers for mqttpi daemons."""

from mqttpi.mqtt.client import MqttConnection, availability_topic_for

__all__ = ["MqttConnection", "availability_topic_for"]
