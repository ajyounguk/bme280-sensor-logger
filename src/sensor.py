# src/sensor.py
import bme280
from datetime import datetime

def read_bme280_data(bus, address, source):
    """Read sensor data from BME280 and return formatted dictionary."""
    calibration_params = bme280.load_calibration_params(bus, address)
    data = bme280.sample(bus, address, calibration_params)

    bme280_data =  {
        "source": source,
        "temperature": round(data.temperature, 2),
        "pressure": round(data.pressure, 2),
        "humidity": round(data.humidity, 2),
        "wind" : None
    }

    return bme280_data

