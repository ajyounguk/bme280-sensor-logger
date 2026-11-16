# BME280 Sensor Logger

Indoor temperature, pressure and humidity from a BME280 on a Raspberry Pi, alongside outdoor readings from the
Met Office. Published to Home Assistant over MQTT and/or logged to MongoDB.

![Home Assistant dashboard](docs/screenshots/HA.png?raw=true)

## What it does

- **Reads a BME280** over I2C at a set interval (default every 10 minutes).
- **Fetches outdoor observations** from the nearest Met Office weather station via the
  [Weather DataHub](https://datahub.metoffice.gov.uk/) Land Observations API (free plan). It polls at most once an
  hour by default and stays well inside the 360 calls/day limit.
- **Publishes to MQTT** for Home Assistant, and/or **stores to MongoDB** for history and charts (MongoDB Atlas and
  Charts both work on the free tier).
- **Runs without hardware:** a fake sensor lets you try it, or develop on it, on Windows or macOS.
- Every output can be switched on or off in the config. The config is validated at start-up, and secrets are never
  logged.

<sub>Example chart: BME280 readings in MongoDB Atlas, charted with MongoDB Charts.</sub>
![MongoDB chart](docs/screenshots/mongoChart.png?raw=true)

## Quick try (any OS, no sensor)

Needs Python 3.11 or later.

```bash
git clone https://github.com/ajyounguk/bme280-sensor-logger
cd bme280-sensor-logger
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python main.py --config config/config-fake.json
```

`config/config-fake.json` uses `"sensor": {"type": "fake"}` and turns off MQTT, MongoDB and the Met Office, so it
just logs plausible readings every 10 seconds:

```
[INFO 2026-11-16 13:28:48] - bme280-sensor-logger starting...
[INFO 2026-11-16 13:28:48] - Sensor: fake (I2C port 1, address 0x76)
[INFO 2026-11-16 13:28:48] - BME280 - Temperature: 21.05 °C, Pressure: 1012.51 hPa, Humidity: 45.88 %
```

To try MQTT or MongoDB without a sensor, copy `config-example.json` as below and set `sensor.type` to `"fake"`.

## Install on a Raspberry Pi

1. Enable I2C: `sudo raspi-config`, then **Interface Options**, **I2C**, **Enable**.
2. Install the tools and clone the repo:
   ```bash
   sudo apt update && sudo apt install -y git python3-venv i2c-tools
   git clone https://github.com/ajyounguk/bme280-sensor-logger
   cd bme280-sensor-logger
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Check that the sensor is visible: `i2cdetect -y 1` should show `76` or `77`. Older 256 MB Pis use bus `0`.
   If it doesn't show, check the wiring. [This guide](https://www.hackster.io/Shilleh/beginner-tutorial-how-to-connect-raspberry-pi-and-bme280-4fdbd5) helps.
4. Create your config (see below), then do a single test run:
   ```bash
   python main.py --once
   ```

## Configuration

```bash
cp config/config-example.json config/config.json
```

`config/config.json` is git-ignored. It's where your API key and passwords go, so keep it out of anything you share.
The app refuses to start while any `YOUR_...` placeholders are left in, and tells you what's wrong.

```json
{
  "app":       { "readingIntervalSeconds": 600, "deviceName": "lounge_pi", "logLevel": "INFO" },
  "sensor":    { "type": "bme280", "i2c_port": 1, "bme280_address": "0x76" },
  "metoffice": { "enabled": true, "APIKey": "YOUR_DATAHUB_LAND_OBSERVATIONS_API_KEY",
                 "latitude": 51.5, "longitude": -0.12, "pollIntervalSeconds": 3600 },
  "mongo":     { "enabled": true, "uri": "mongodb+srv://MONGO_USERNAME:MONGO_PASSWORD@cluster0.example.mongodb.net/?retryWrites=true&w=majority",
                 "dbName": "YOUR_DB_NAME", "collection": "house_temperature_readings",
                 "sensorSource": "lounge", "metofficeSource": "outside" },
  "mqtt":      { "enabled": true, "broker": "homeassistant.local", "port": 1883,
                 "mqttUsername": "YOUR_MQTT_USERNAME", "mqttPassword": "YOUR_MQTT_PASSWORD",
                 "sensorTopic": "homeassistant/bme280_lounge", "metofficeTopic": "homeassistant/metoffice" }
}
```

| Key | Meaning |
| --- | --- |
| `app.readingIntervalSeconds` | Seconds between sensor readings (5 to 86400) |
| `app.deviceName` | Tags MQTT messages and MongoDB documents |
| `app.logLevel` | `DEBUG`, `INFO` (default), `WARNING` or `ERROR` |
| `sensor.type` | `bme280` (default), or `fake` for no hardware |
| `sensor.i2c_port` | I2C bus, usually `1` |
| `sensor.bme280_address` | `"0x76"` or `"0x77"` |
| `metoffice.enabled` | Fetch outdoor observations |
| `metoffice.APIKey` | Your DataHub **Land Observations** key (see below) |
| `metoffice.latitude` / `longitude` | Your location. The nearest station is looked up once at start-up |
| `metoffice.geohash` | Optional: a station geohash, used instead of lat/lon |
| `metoffice.pollIntervalSeconds` | How often to call the API. Default 3600, minimum 300 |
| `mongo.enabled`, `uri`, `dbName`, `collection` | MongoDB connection and target |
| `mongo.sensorSource` / `metofficeSource` | `source` label on sensor and Met Office readings. Also used in MQTT messages |
| `mqtt.enabled`, `broker`, `port` | MQTT broker (default port 1883) |
| `mqtt.mqttUsername` / `mqttPassword` | Broker credentials. Leave both empty for an anonymous broker |
| `mqtt.sensorTopic` / `metofficeTopic` | Topics for each kind of reading |

### Met Office DataHub key

The Met Office retired DataPoint in 2025. Outdoor readings now come from Weather DataHub's **Land Observations**
API: hourly measurements from about 150 UK stations.

1. Register at [datahub.metoffice.gov.uk](https://datahub.metoffice.gov.uk/).
2. Subscribe to **Land Observations** on the **free plan** (360 calls/day). It's a separate subscription from
   Site Specific forecasts, and its key is different.
3. Put the key in `metoffice.APIKey` in `config/config.json`.

Observations update hourly, so the default `pollIntervalSeconds` of 3600 is plenty. The app also keeps its own
daily call budget. If the API ever returns "quota exceeded", it pauses Met Office calls until midnight UTC, when
the quota resets. The sensor keeps running either way.

> **Upgrading from v1:** `metoffice.locationID` was a DataPoint ID. Replace it with `latitude` and `longitude`, and
> use a DataHub key. The app tells you if an old config is still in place. Met Office wind is now in m/s;
> DataPoint reported mph.

## Run it

```bash
python main.py                      # run forever with config/config.json
python main.py --once               # one reading, then exit
python main.py --config other.json  # another config file
```

### Keep it running with pm2

[pm2](https://pm2.keymetrics.io/) keeps the app running and starts it on boot. It handles Python apps fine.

```bash
sudo apt install -y nodejs npm && sudo npm install -g pm2
pm2 startup          # then run the command it prints
pm2 start main.py --name bme280 --interpreter .venv/bin/python
pm2 save
pm2 logs bme280      # view logs; also: pm2 status / restart bme280 / stop bme280
```

## Home Assistant

Run an MQTT broker (the Mosquitto add-on is the easy route) with a dedicated user for this app. Then add sensors
to `configuration.yaml`:

```yaml
mqtt:
  sensor:
    - name: "BME280 Temperature"
      state_topic: "homeassistant/bme280_lounge"
      unit_of_measurement: "°C"
      device_class: temperature
      value_template: "{{ value_json.temperature }}"
    - name: "BME280 Pressure"
      state_topic: "homeassistant/bme280_lounge"
      unit_of_measurement: "hPa"
      device_class: pressure
      value_template: "{{ value_json.pressure }}"
    - name: "BME280 Humidity"
      state_topic: "homeassistant/bme280_lounge"
      unit_of_measurement: "%"
      device_class: humidity
      value_template: "{{ value_json.humidity }}"
    - name: "Met Office Temperature"
      state_topic: "homeassistant/metoffice"
      unit_of_measurement: "°C"
      device_class: temperature
      value_template: "{{ value_json.temperature }}"
    - name: "Met Office Pressure"
      state_topic: "homeassistant/metoffice"
      unit_of_measurement: "hPa"
      device_class: pressure
      value_template: "{{ value_json.pressure }}"
    - name: "Met Office Humidity"
      state_topic: "homeassistant/metoffice"
      unit_of_measurement: "%"
      device_class: humidity
      value_template: "{{ value_json.humidity }}"
    - name: "Met Office Wind Speed"
      state_topic: "homeassistant/metoffice"
      unit_of_measurement: "m/s"
      device_class: wind_speed
      value_template: "{{ value_json.wind }}"
```

To watch the raw messages, go to **Settings**, **Devices & services**, **MQTT**, **Configure**, and listen on your
topic.

![MQTT listener](docs/screenshots/MQTT.png?raw=true)
![Home Assistant history](docs/screenshots/HA2.png?raw=true)

Message payloads:

```json
// sensorTopic
{"source": "lounge", "temperature": 21.05, "pressure": 1012.51, "humidity": 45.88, "wind": null}
// metofficeTopic (re-sent every cycle with the latest observation)
{"source": "outside", "temperature": 9.13, "humidity": 85.0, "pressure": 1025.0, "wind": 1.4,
 "observedAt": "2026-11-16T10:00:00Z", "deviceName": "lounge_pi"}
```

## MongoDB

Each reading becomes one document:

```json
{ "source": "lounge", "timestamp": "2026-11-16T10:12:00Z", "temperature": 21.05, "pressure": 1012.51,
  "humidity": 45.88, "wind": null, "deviceName": "lounge_pi" }
```

Met Office documents also carry `observedAt`, the station's observation time. Each observation is stored once,
even when several devices share a collection with the same `metofficeSource`. Visualise the data with
[MongoDB Charts](https://www.mongodb.com/products/charts).

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest              # all tests; the sensor, MQTT, MongoDB and Met Office are faked
ruff check . && ruff format .
```

- No network, broker, database or hardware is needed. The Met Office tests use recorded-style fixtures in
  `tests/fixtures/`.
- `tests/test_hardware.py` reads a real BME280. It's skipped unless it runs on Linux with `/dev/i2c-1` present.
  On the Pi: `pytest -m hardware -v`. Set `BME280_I2C_PORT` / `BME280_ADDRESS` if yours differ.
- CI runs ruff and pytest on Ubuntu and Windows (Python 3.11 and 3.13). Dependabot keeps the pinned versions fresh.
- Code layout and design decisions: [docs/design.md](docs/design.md). API notes:
  [docs/metoffice-datahub.md](docs/metoffice-datahub.md).

## To do

- Publish in Home Assistant MQTT auto-discovery format, so the YAML above isn't needed.

## Licence

MIT. See [LICENSE](LICENSE).
