"""BME280 sensor access, plus a fake sensor for running without hardware (e.g. on Windows)."""

from __future__ import annotations

import random
from typing import Protocol

from src.config import SensorConfig


class Sensor(Protocol):
    def read(self) -> dict: ...


def _reading(source: str, temperature: float, pressure: float, humidity: float) -> dict:
    # Payload shape is published as-is to MQTT and Mongo: keep keys stable (Home Assistant templates use them).
    return {
        "source": source,
        "temperature": round(temperature, 2),
        "pressure": round(pressure, 2),
        "humidity": round(humidity, 2),
        "wind": None,
    }


class Bme280Sensor:
    """Reads a BME280 over I2C. The bus is opened per read so a glitch on one read doesn't wedge the next."""

    def __init__(self, i2c_port: int, address: int, source: str):
        # Imported here so the app (and tests) run on machines without the hardware libraries.
        import bme280
        import smbus2

        self._bme280 = bme280
        self._smbus2 = smbus2
        self.i2c_port = i2c_port
        self.address = address
        self.source = source

    def read(self) -> dict:
        with self._smbus2.SMBus(self.i2c_port) as bus:
            calibration = self._bme280.load_calibration_params(bus, self.address)
            data = self._bme280.sample(bus, self.address, calibration)
        return _reading(self.source, data.temperature, data.pressure, data.humidity)


class FakeSensor:
    """Plausible indoor readings that drift slowly, for development and tests."""

    def __init__(self, source: str, seed: int | None = None):
        self.source = source
        self._rng = random.Random(seed)
        self._t, self._p, self._h = 21.0, 1013.0, 45.0

    def read(self) -> dict:
        self._t = min(max(self._t + self._rng.uniform(-0.2, 0.2), 15.0), 28.0)
        self._p = min(max(self._p + self._rng.uniform(-0.5, 0.5), 980.0), 1040.0)
        self._h = min(max(self._h + self._rng.uniform(-1.0, 1.0), 30.0), 70.0)
        return _reading(self.source, self._t, self._p, self._h)


def build_sensor(cfg: SensorConfig) -> Sensor:
    if cfg.type == "fake":
        return FakeSensor(cfg.source)
    return Bme280Sensor(cfg.i2c_port, cfg.address, cfg.source)
