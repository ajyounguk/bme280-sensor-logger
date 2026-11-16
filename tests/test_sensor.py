import sys
import types
from collections import namedtuple

import pytest

from src.config import SensorConfig
from src.sensor import Bme280Sensor, FakeSensor, build_sensor

KEYS = {"source", "temperature", "pressure", "humidity", "wind"}


def test_fake_sensor_payload_shape_and_ranges():
    s = FakeSensor("lounge", seed=1)
    for _ in range(500):
        r = s.read()
        assert set(r) == KEYS
        assert r["source"] == "lounge"
        assert r["wind"] is None
        assert 15 <= r["temperature"] <= 28
        assert 980 <= r["pressure"] <= 1040
        assert 30 <= r["humidity"] <= 70


def test_fake_sensor_is_deterministic_with_seed():
    assert FakeSensor("x", seed=7).read() == FakeSensor("x", seed=7).read()


def test_build_sensor_fake():
    assert isinstance(build_sensor(SensorConfig("fake", 1, 0x76, "lounge")), FakeSensor)


@pytest.fixture
def fake_hw_libs(monkeypatch):
    """Stand-ins for smbus2 and bme280 so the real-sensor code path runs anywhere."""
    opened = []

    class SMBus:
        def __init__(self, port):
            self.port = port
            self.closed = False
            opened.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.closed = True

    Sample = namedtuple("Sample", "temperature pressure humidity")
    smbus2 = types.SimpleNamespace(SMBus=SMBus)
    bme280 = types.SimpleNamespace(
        load_calibration_params=lambda bus, addr: {"addr": addr},
        sample=lambda bus, addr, cal: Sample(21.456, 1012.345, 44.444),
    )
    monkeypatch.setitem(sys.modules, "smbus2", smbus2)
    monkeypatch.setitem(sys.modules, "bme280", bme280)
    return opened


def test_bme280_sensor_reads_and_closes_bus(fake_hw_libs):
    s = build_sensor(SensorConfig("bme280", 1, 0x77, "lounge"))
    assert isinstance(s, Bme280Sensor)
    assert s.read() == {"source": "lounge", "temperature": 21.46, "pressure": 1012.35, "humidity": 44.44, "wind": None}
    assert fake_hw_libs[0].port == 1
    assert fake_hw_libs[0].closed
