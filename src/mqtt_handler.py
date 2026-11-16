"""MQTT publishing (paho-mqtt 2.x).

Connects per cycle, like the original: with a long reading interval this is simpler and more robust than holding
a connection open across broker restarts. The network loop runs while publishing so QoS 1 messages are actually
delivered before disconnecting.
"""

from __future__ import annotations

import json
import logging
import threading

import paho.mqtt.client as mqtt

from src.config import MqttConfig

log = logging.getLogger(__name__)

CONNECT_TIMEOUT = 10  # seconds
PUBLISH_TIMEOUT = 10  # seconds


class MQTTHandler:
    def __init__(self, cfg: MqttConfig, client_id: str, client_factory=mqtt.Client):
        self._cfg = cfg
        self._client_id = client_id
        self._client_factory = client_factory
        self.client = None

    def connect(self) -> bool:
        connack = threading.Event()
        result = {}

        def on_connect(_client, _userdata, _flags, reason_code, _properties):
            result["reason"] = reason_code
            connack.set()

        client = None
        try:
            client = self._client_factory(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=self._client_id
            )
            client.on_connect = on_connect
            if self._cfg.username:
                client.username_pw_set(self._cfg.username, self._cfg.password or None)
            client.connect(self._cfg.broker, self._cfg.port, keepalive=60)
            client.loop_start()
            # TCP connect succeeding doesn't mean the broker accepted us (e.g. bad credentials): wait for CONNACK.
            if not connack.wait(CONNECT_TIMEOUT):
                raise TimeoutError(f"no CONNACK within {CONNECT_TIMEOUT} s")
            if result["reason"].is_failure:
                raise ConnectionRefusedError(f"broker refused connection: {result['reason']}")
        except Exception as e:  # noqa: BLE001 - socket/DNS/auth errors vary; log and carry on without MQTT
            log.error("Failed to connect to MQTT broker %s:%s: %s", self._cfg.broker, self._cfg.port, e)
            if client is not None:
                try:
                    client.loop_stop()
                except Exception:  # noqa: BLE001, S110
                    pass
            self.client = None
            return False
        self.client = client
        log.debug("Connected to MQTT broker %s:%s", self._cfg.broker, self._cfg.port)
        return True

    def publish(self, topic: str, data: dict) -> bool:
        if not self.client:
            return False
        try:
            info = self.client.publish(topic, json.dumps(data), qos=1)
            info.wait_for_publish(timeout=PUBLISH_TIMEOUT)
            if not info.is_published():
                log.error("MQTT publish to %s not confirmed within %s s", topic, PUBLISH_TIMEOUT)
                return False
        except Exception as e:  # noqa: BLE001
            log.error("MQTT publish to %s failed: %s", topic, e)
            return False
        return True

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.disconnect()
                self.client.loop_stop()
            finally:
                self.client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.disconnect()
