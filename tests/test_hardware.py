"""Real-hardware test: reads an actual BME280. Skipped unless running on Linux with the I2C bus present.

On the Pi:  pytest -m hardware -v
Override the bus/address with BME280_I2C_PORT / BME280_ADDRESS (e.g. 0x77) if yours differ.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

I2C_PORT = int(os.environ.get("BME280_I2C_PORT", "1"))
ADDRESS = int(os.environ.get("BME280_ADDRESS", "0x76"), 16)

_reason = None
if not sys.platform.startswith("linux"):
    _reason = "needs Linux (Raspberry Pi)"
elif not Path(f"/dev/i2c-{I2C_PORT}").exists():
    _reason = f"/dev/i2c-{I2C_PORT} not found (enable I2C with raspi-config)"
elif not (importlib.util.find_spec("smbus2") and importlib.util.find_spec("bme280")):
    _reason = "smbus2 / RPi.bme280 not installed"

pytestmark = [pytest.mark.hardware, pytest.mark.skipif(_reason is not None, reason=_reason or "")]


def test_real_bme280_reading_is_plausible():
    from src.sensor import Bme280Sensor

    r = Bme280Sensor(I2C_PORT, ADDRESS, "hardware-test").read()
    assert -40 <= r["temperature"] <= 85  # BME280 operating range
    assert 300 <= r["pressure"] <= 1100
    assert 0 <= r["humidity"] <= 100
