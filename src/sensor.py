# src/sensor.py
import smbus2
import bme280
from datetime import datetime

def read_bme280_data(address, port, source):

    # Create I2C bus
    bus = None
    bus = smbus2.SMBus(port)

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

    bus.close()  

    return bme280_data


