"""Shared fixtures and fakes. Nothing here touches hardware, the network, a broker or a database."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


VALID_RAW = {
    "app": {"readingIntervalSeconds": 600, "deviceName": "test_pi", "logLevel": "INFO"},
    "sensor": {"type": "fake", "i2c_port": 1, "bme280_address": "0x76"},
    "metoffice": {
        "enabled": True,
        "APIKey": "test-key-123",
        "latitude": 51.5,
        "longitude": -0.12,
        "pollIntervalSeconds": 3600,
    },
    "mongo": {
        "enabled": True,
        "uri": "mongodb+srv://user:s3cret@cluster0.example.mongodb.net/?retryWrites=true",
        "dbName": "readings",
        "collection": "house",
        "sensorSource": "lounge",
        "metofficeSource": "outside",
    },
    "mqtt": {
        "enabled": True,
        "broker": "broker.test",
        "port": 1883,
        "mqttUsername": "logger",
        "mqttPassword": "mqtt-pass",
        "sensorTopic": "homeassistant/bme280_test",
        "metofficeTopic": "homeassistant/metoffice",
    },
}


@pytest.fixture
def raw_config():
    return copy.deepcopy(VALID_RAW)


# --- requests fake -------------------------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self._text = text

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def json(self):
        if self._text is not None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Routes GETs by the last path segment: 'nearest' or anything else (a geohash)."""

    def __init__(self, routes=None):
        self.headers = {}
        self.calls = []
        self.routes = routes or {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        key = url.rsplit("/", 1)[-1]
        route = self.routes.get(key, self.routes.get("*"))
        if isinstance(route, Exception):
            raise route
        if callable(route):
            return route(url, params)
        return route if route is not None else FakeResponse(404, {})


@pytest.fixture
def fake_session():
    return FakeSession(
        {
            "nearest": FakeResponse(200, load_fixture("nearest.json")),
            "*": FakeResponse(200, load_fixture("observations.json")),
        }
    )


# --- paho fake -----------------------------------------------------------------------------------------------


class FakeMessageInfo:
    def __init__(self, published=True):
        self._published = published

    def wait_for_publish(self, timeout=None):
        pass

    def is_published(self):
        return self._published


class FakeReasonCode:
    def __init__(self, failure=False, text="Success"):
        self.is_failure = failure
        self._text = text

    def __str__(self):
        return self._text


class FakeMqttClient:
    instances: list[FakeMqttClient] = []

    def __init__(
        self,
        callback_api_version=None,
        client_id=None,
        fail_connect=False,
        publish_ok=True,
        connack=FakeReasonCode(),  # noqa: B008
    ):
        self.callback_api_version = callback_api_version
        self.client_id = client_id
        self.fail_connect = fail_connect
        self.publish_ok = publish_ok
        self.connack = connack  # None = broker never answers
        self.on_connect = None
        self.credentials = None
        self.connected_to = None
        self.loop_running = False
        self.published = []
        FakeMqttClient.instances.append(self)

    def username_pw_set(self, username, password=None):
        self.credentials = (username, password)

    def connect(self, host, port, keepalive=60):
        if self.fail_connect:
            raise ConnectionRefusedError("refused")
        self.connected_to = (host, port)

    def loop_start(self):
        self.loop_running = True
        if self.connack is not None and self.on_connect:
            self.on_connect(self, None, {}, self.connack, None)

    def loop_stop(self):
        self.loop_running = False

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, json.loads(payload), qos))
        return FakeMessageInfo(self.publish_ok)

    def disconnect(self):
        self.connected_to = None


@pytest.fixture
def mqtt_client_factory():
    FakeMqttClient.instances = []
    return FakeMqttClient


# --- pymongo fake --------------------------------------------------------------------------------------------


class FakeCollection:
    def __init__(self):
        self.docs = []
        self.fail = None

    def insert_one(self, doc):
        if self.fail:
            raise self.fail
        self.docs.append(dict(doc))

    def find_one(self, query, projection=None):
        if self.fail:
            raise self.fail
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return d
        return None


class FakeMongoClient:
    def __init__(self, uri, **kwargs):
        self.uri = uri
        self.kwargs = kwargs
        self.closed = False
        self._dbs = {}

    def __getitem__(self, db):
        return self._dbs.setdefault(db, _FakeDb())

    def close(self):
        self.closed = True


class _FakeDb:
    def __init__(self):
        self._cols = {}

    def __getitem__(self, name):
        return self._cols.setdefault(name, FakeCollection())
