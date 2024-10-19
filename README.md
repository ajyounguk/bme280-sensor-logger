# BME280 Temperature Sensor (Python)

This Python-based application monitors environmental data using a BME280 sensor and the Met Office API. Temperature, pressure and humdity readings can then be persisted in a Mongo database, or sent to a MQTT for integration with Home Assistant .

## Features

Data collection:
- BM280 Sensor - Captures temperature, humidity, and pressure data from the BME280 sensor. The application captures data from the BME280 sensor at regular intervals defined in the config.
- Met Office API: Fetches external / outdoor weather data to enhance your sensor's readings.

Data persistency:
- MQTT: Publishes data to an MQTT broker for real-time monitoring (e.g., Home Assistant).
- MongoDB: Logs sensor and Met Office data to MongoDB for historical records.

Configuration File:
Configuration parameters in .json file for reading frequency, sensor, MetOffice, Mongo and MQQT parameters. 

<sub>example Chart generated from BME280 data posted to Mongo Atlas and charted with Mongo Charts (all in free tier)<sub>
![MongoChart](/screenshots/mongoChart.png?raw=true)

## High level code logic
1. load configuration parameters from /config/config.json
2. main loop
3. get sensor readings
4. post sensor data to MQTT (if enabled in config)
5. post sensor data to Mongo (if enabled in config)
6. get MetOffice readings (if enabled in config)
7. post MetOffice data to MQTT (if enabled in config)
8. post MetOffice data to Mongo (if enabled in config)
9. sleep for configurable amount of seconds & loop to 2

## Application structure

- Main 
/main.py = main application 

- Python Modules
/src/sensor.py = BME280 integration code
/src/metoffice.py = MetOffice API integration code
/src/mongo.py = Mongo database integration code
/src/mqtt_handler = MQTT handler code (can be used for integration with Home Assistant)


## Installation
- Update OS packages
```bash
sudo apt-get update
```

- Install git
```bash
sudo apt-get install git
```

- Clone the repository
```bash
git clone https://github.com/ajyounguk/bme280-sensor-logger
```

- Update your OS environment
```bash
sudo apt update
```
```bash
sudo apt install python3-pip
```


-  Activate a Python Virtual Environment
 install venv if not available
```bash
sudo apt install python3-venv
```

```bash
python3 -m venv venv
```
```bash
source venv/bin/activate
```


- Install Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

- Copy the example config file to config.json
```bash
cd config
```
```bash
cp example-config.json config.json
```
- Customise the configuration filewith your MongoDB, MQTT, and Met Office credentials as per below:

Application:
- `readingIntervalSeconds` - Application interval between sensor and MetOffice readings
- `deviceName` - Name for this device, used to tag Mongo and MQTT records


Sensor:
- `i2c_port`: Port number (typically 1).
- `bme280_address`: The default I2C address for the BME280 sensor (varies between 0x76 and 0x77).


MetOffice:
- `enabled`: Enable or disable MetOffice data integration
- `locationID`: Numeric value for the MetOffice location where data is collected (see notes below).
- `APIKey`:  Your MetOffice API key (can be obtained [here](https://www.metoffice.gov.uk/services/data/datapoint/api)).

> The `locationID` denotes your weather data location. You may find success using 4-digit location IDs, often representing larger regions or Counties in the UK. See [this list](https://gist.github.com/ajyounguk/e05db10df74e0b86c7e6a0a39a95f1f4) for more.


Mongo:
- `enabled`: Enable or disable MongoDB data integration
- `uri`: Connection string for your Mongo database
- `dbName`: Mongo database name
- `collection`: collection name for storing readings.
- `sensorSource`: source name for the bme280 documents stored in mongo
- `metofficeSource`: source name for the MetOffice documents stored in mongo


MQTT:
- `enabled`: Enable or disable MQTT data integration
- `broker`: IP address or FQDN for the MQTT Broker (For Home Assistant this is the address of your Home Assistant host)
- `port`: 1833 is the default port
- `mqttUsername`: MQTT username (for Home Assistant, use a dedicated user created for MQTT)
- `mqttPassword`: The corresponding MQTT password.
- `sensorTopic`: MQTT topic name to receive the bme280 sensor data 
- `metofficeTopic`: MQTT topic name to receive the MetOffice data

Example configuration.json:
```json
{
  "app": {
      "readingIntervalSeconds": 600,
      "deviceName": "lounge_rpi"
  },
  "sensor": {
      "i2c_port": 1,
      "bme280_address": "0x76"
  },
  "metoffice": {
      "enabled": true,
      "locationID": "3414",  
      "APIKey": "YOUR_METOFFICE_API_KEY"           
  },
  "mongo": {
      "enabled" : true,
      "uri": "mongodb+srv://MONGO_USERNAME:MONGO_PASSWORD@cluster0.1haxi.mongodb.net/DATABASE?retryWrites=true&w=majority",
      "dbName": "YOUR_DB_NAME",
      "collection": "house_temperature_readings",
      "sensorSource": "lounge",
      "metofficeSource": "shropshire_outside"
  },
  "mqtt": {
      "enabled": true,
      "broker": "192.168.1.250",
      "port": 1883,
      "mqttUsername": "YOUR_MQTT_USERNAME",
      "mqttPassword": "YOUR_MQTT_PASSWORD",
      "sensorTopic": "homeassistant/bme280_lounge",
      "metofficeTopic": "homeassistant/metoffice"
  }
}
```

## Run the Application:

```bash
python main.py
```

## Sample Output
```
[INFO 2024-10-19 16:29:47] - Connected to MQTT broker at 192.168.1.250:1883
[INFO 2024-10-19 16:29:47] - I2C Port: 1, BME280 Address: 118
[INFO 2024-10-19 16:29:47] - Reading Interval: 30 seconds
[INFO 2024-10-19 16:29:47] - MongoDB Enabled: True
[INFO 2024-10-19 16:29:47] - Met Office Enabled: True
[INFO 2024-10-19 16:29:47] - MQTT Enabled: True
[INFO 2024-10-19 16:29:47] - BME280 - Temperature: 23.44 °C, Pressure: 1001.85 hPa, Humidity: 47.63 %
[INFO 2024-10-19 16:29:48] - MetOffice - Temperature: 15.7 °C, Humidity: 58.3 %, Pressure: 1011.0 hPa, Wind: 6.0 m/s
[INFO 2024-10-19 16:30:19] - BME280 - Temperature: 23.44 °C, Pressure: 1001.87 hPa, Humidity: 47.45 %
[INFO 2024-10-19 16:30:20] - MetOffice - Temperature: 15.7 °C, Humidity: 58.3 %, Pressure: 1011.0 hPa, Wind: 6.0 m/s
```


# Additional Information

#### MongoDB

MongoDB can be hosted anywhere. The app works well with a free-tier Mongo Atlas cloud database. See [MongoDB Atlas](https://cloud.mongodb.com).

- The `sensorSource` configuration is used to populate the `source` field for sensor reading data in Mongo, allowing multiple devices to store readings in the same collection.
- The `metofficeSource` configuration is used to populate the `source` field for MetOffice data documents. 
- The MongoDB document structure looks like this:
```json
{
  "source": "lounge",
  "temperature": 22.5,
  "humidity": 55.2,
  "pressure": 1012.8,
  "wind": 5.6,  // Only for Met Office data documents, Null for BME280 readings
  "timestamp": "2024-10-19T15:11:21.031+00:00",
}
```


You can visualize data from different devices using MongoDB Charts. See [MongoDB Charts](https://www.mongodb.com/products/charts).




#### MetOffice

- MetOffice readings typically only updated once per hour.
- In oder to avoid redundant MetOffice readings, the code checks if a MetOffice document already exists  in the Mongo database, if so it will skip creating another.
- THis also ensures that if you are running multiple sensors, only a single MetOffice record is created in each hourly interval.


#### BME280 Sensor

Ensure that I2C is enabled on the Pi via `raspi-config` (under `Interface Options` > `I2C`):

```bash
sudo raspi-config
```

- The sensor typically operates on an I2C bus. To ensure proper communication, verify the bus number and address configuration. You can use `i2cdetect` to verify if your sensor is detected correctly.

To detect the port number for the BME280 sensor, use this command (note: the bus port may vary depending on the Pi model):

```bash
# install i2cdetect
sudo apt-get update
sudo apt-get install i2c-tools
```

```bash
i2cdetect -y 1 # for newwer models
i2cdetect -y 0  # for older 256MB Raspberry Pi
```
- In case of errors, double-check the wiring and bus settings. [There is a guide here](https://www.hackster.io/Shilleh/beginner-tutorial-how-to-connect-raspberry-pi-and-bme280-4fdbd5)


#### Home Assistant Integration

For those using Home Assistant, you can use the MQTT integration to display temperature, pressure, and humidity data from your sensors. 

Home assistant integration is beyond the scope of this README, there are many better guides on the web for this. 
I recommend starting with the MQTT mosquito add-on for Home Assistant. Then configure the MQTT device integration. A separate credential (Home Assistant person) is recommended to provide access controls for the MQTT integration. Use the same credentials in the MQTT configuration for this application (`mqttUsername` and `mqttPassword`).

Finally you will need to configure your Home Assistant `configuration.yaml` file to listen to the relevant MQTT topics and define the devices/entities for the sensor readings in line with the example below:

> [todo 10/2024] Post data in the format for Home Assistant autodiscovery 

```yaml
mqtt:
  sensor:
    - name: "BME280 Temperature"
      state_topic: "homeassistant/bme280_lounge"
      unit_of_measurement: "°C"
      value_template: "{{ value_json.temperature }}"
  
    - name: "BME280 Pressure"
      state_topic: "homeassistant/bme280_lounge"
      unit_of_measurement: "hPa"
      value_template: "{{ value_json.pressure }}"
  
    - name: "BME280 Humidity"
      state_topic: "homeassistant/bme280_lounge"
      unit_of_measurement: "%"
      value_template: "{{ value_json.humidity }}"
  
    - name: "BME280 Wind Speed"
      state_topic: "homeassistant/bme280_lounge"
      unit_of_measurement: "m/s"
      value_template: "{{ value_json.wind }}"
  
    - name: "Met Office Temperature"
      state_topic: "homeassistant/metoffice"
      unit_of_measurement: "°C"
      value_template: "{{ value_json.temperature }}"
  
    - name: "Met Office Pressure"
      state_topic: "homeassistant/metoffice"
      unit_of_measurement: "hPa"
      value_template: "{{ value_json.pressure }}"
  
    - name: "Met Office Humidity"
      state_topic: "homeassistant/metoffice"
      unit_of_measurement: "%"
      value_template: "{{ value_json.humidity }}"
  
    - name: "Met Office Wind Speed"
      state_topic: "homeassistant/metoffice"
      unit_of_measurement: "m/s"
      value_template: "{{ value_json.wind }}"
```
Home Assistant Screenshots

![HA](/screenshots/HA.png?raw=true)

![HA2](/screenshots/HA2.png?raw=true)
