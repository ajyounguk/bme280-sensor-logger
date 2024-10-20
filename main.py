# bme280-temperature-sensor (python version)
# This Python-based application monitors environmental data using a BME280 sensor 
# and the Met Office API. 
# Temperature, pressure and humdity readings can be persisted in a Mongo database,
# or sent to a MQTT for integration with Home Assistant .

# Code logic at a high level:
# 1. load configuration parameters from /config/config.json
# 2. main loop
#   2.2 get sensor readings
#   2.3 post sensor data to MQTT (if enabled in config)
#   2.3 post sensor data to Mongo (if enabled in config)
#   2.4 get MetOffice readings (if enabled in config)
#   2.3 post MetOffice data to MQTT (if enabled in config)
#   2.3 post MetOffice data to Mongo (if enabled in config)
# 3. sleep for configurable amount of seconds & loop to 2.


# imports
import json
import time
from datetime import datetime
from src.mongo import insert_mongo_data, hourDataFound # Removed document_exists as it's now handled in insert_data
from src.metoffice import get_met_office_data
from src.mqtt_handler import MQTTHandler
from src.sensor import read_bme280_data

# Load configuration from JSON file
def load_config():
    with open('config/config.json') as config_file:
        return json.load(config_file)

# Main logic to read from sensors and process data
def main_loop(mqtt_handler):
    while True:

        # added to main loop due to diconnects and timeouts
        mqtt_handler = None
        if MQTT_ENABLED:
            mqtt_handler = MQTTHandler(MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD)
            mqtt_handler.connect()

        # read sensor data
        bme280_data = read_bme280_data(I2C_PORT, BME280_ADDRESS, SENSOR_SOURCE)

        # Print BME280 data
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - BME280 - Temperature: {bme280_data['temperature']} °C, "
              f"Pressure: {bme280_data['pressure']} hPa, Humidity: {bme280_data['humidity']} %")

        
        # Publish BME280 data to MQTT if enabled
        if MQTT_ENABLED:
            mqtt_handler.publish(MQTT_TOPIC_BME280, bme280_data)

        
        # Insert BME280 data into MongoDB
        if MONGO_ENABLED:
            insert_mongo_data(MONGO_URI, DATABASE_NAME, COLLECTION_NAME, bme280_data, DEVICE_NAME)
        
     
        # Fetch and insert Met Office data if enabled
        if METOFFICE_ENABLED:
            met_office_data_doc = get_met_office_data(LOCATION_ID, API_KEY, METOFFICE_SOURCE)
            if met_office_data_doc:

                met_office_data_doc["deviceName"] = DEVICE_NAME
                
                # Print Met Office data if it was inserted
                print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MetOffice - Temperature: {met_office_data_doc['temperature']} °C, "
                      f"Humidity: {met_office_data_doc['humidity']} %, Pressure: {met_office_data_doc['pressure']} hPa, "
                      f"Wind: {met_office_data_doc['wind']} m/s")

                # Publish Met Office data to MQTT if enabled
                if MQTT_ENABLED:
                    mqtt_handler.publish(MQTT_TOPIC_METOFFICE, met_office_data_doc)
                
                # Insert Met Office data into MongoDB, checking for existing records
                if MONGO_ENABLED:
                    # MetOffice data is only updated ever hour
                    # therefore to avoid redundant documents being created in Mongo we check to see 
                    # if there is already a document created in the database in the current hour slot first
                    if (hourDataFound(MONGO_URI, DATABASE_NAME, COLLECTION_NAME, METOFFICE_SOURCE ) != True):
                        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Posting MetOffice readings for this hour")
                        insert_mongo_data(MONGO_URI, DATABASE_NAME, COLLECTION_NAME, met_office_data_doc, DEVICE_NAME)
            else:
                print("[ERROR {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Failed to fetch Met Office data.")

        if MQTT_ENABLED:
            if mqtt_handler:
                mqtt_handler.disconnect()

        # Sleep for the specified interval before the next reading
        time.sleep(READING_INTERVAL)

# Main execution
if __name__ == "__main__":
    config = load_config()

    # App configuration values
    READING_INTERVAL = config['app']['readingIntervalSeconds']
    DEVICE_NAME = config['app']['deviceName']

    # Sensor configuration valus
    I2C_PORT = config['sensor']['i2c_port']
    BME280_ADDRESS = int(config['sensor']['bme280_address'], 16)

    # MongoDB settings from the config file
    MONGO_ENABLED = config['mongo']['enabled']
    MONGO_URI = config['mongo']['uri']
    DATABASE_NAME = config['mongo']['dbName']
    COLLECTION_NAME = config['mongo']['collection']
    SENSOR_SOURCE = config['mongo']['sensorSource']  # Get sensor source from config
    METOFFICE_SOURCE = config['mongo']['metofficeSource']  # Get Met Office source from config

    # Met Office settings from the config file
    METOFFICE_ENABLED = config['metoffice']['enabled']
    LOCATION_ID = config['metoffice']['locationID']
    API_KEY = config['metoffice']['APIKey']

    # MQTT broker settings from the config file
    MQTT_ENABLED = config['mqtt']['enabled']  # Check if MQTT is enabled
    MQTT_BROKER = config['mqtt']['broker']
    MQTT_PORT = config['mqtt']['port']
    MQTT_USERNAME = config['mqtt']['mqttUsername']
    MQTT_PASSWORD = config['mqtt']['mqttPassword']
    MQTT_TOPIC_BME280 = config['mqtt']['sensorTopic']
    MQTT_TOPIC_METOFFICE = config['mqtt']['metofficeTopic']

    

    print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - bme280-temperature-logger starting...")
    
    # General App Configuration
    print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Device Name: {DEVICE_NAME}")
    print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Reading Interval: {READING_INTERVAL} seconds")
    
    # Sensor Configuration
    print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - I2C Port: {I2C_PORT}")
    print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - BME280 Address: {BME280_ADDRESS}")

    # MongoDB Configuration
    print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MongoDB Enabled: {MONGO_ENABLED}")
    if MONGO_ENABLED:
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MongoDB URI: {MONGO_URI}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MongoDB Database: {DATABASE_NAME}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MongoDB Collection: {COLLECTION_NAME}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Sensor Source: {SENSOR_SOURCE}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MetOffice Source: {METOFFICE_SOURCE}")

    # Met Office Configuration
    print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Met Office Enabled: {METOFFICE_ENABLED}")
    if METOFFICE_ENABLED:
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Met Office Location ID: {LOCATION_ID}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Met Office API Key: {API_KEY}")

    # MQTT Configuration
    print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MQTT Enabled: {MQTT_ENABLED}")
    if MQTT_ENABLED:
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MQTT Broker: {MQTT_BROKER}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MQTT Port: {MQTT_PORT}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MQTT Username: {MQTT_USERNAME}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MQTT Password: {MQTT_PASSWORD}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MQTT Sensor Topic: {MQTT_TOPIC_BME280}")
        print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - MQTT Met Office Topic: {MQTT_TOPIC_METOFFICE}")

    try:
        main_loop(mqtt_handler)
    except KeyboardInterrupt:
        print("[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Program stopped by user.")
    except Exception as e:
        print(f"[ERROR {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - An error occurred: {e}")
    finally:
        bus.close()  # Ensure the I2C bus is closed on exit
        if mqtt_handler:
            mqtt_handler.disconnect()  # Disconnect MQTT client if it was created
        print("[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - I2C bus closed.")
