import json
import paho.mqtt.client as mqtt
from datetime import datetime

class MQTTHandler:
    def __init__(self, broker, port, username, password):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.client = None

    def connect(self):
        try:
            self.client = mqtt.Client()
            self.client.username_pw_set(self.username, self.password)
            self.client.connect(self.broker, self.port, 60)
            print(f"[INFO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Connected to MQTT broker at {self.broker}:{self.port}")
        except Exception as e:
            print(f"[ERROR {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Failed to connect to MQTT broker: {e}")
            self.client = None

    def publish(self, topic, data):
        if self.client:
            self.client.publish(topic, json.dumps(data))

    def disconnect(self):
        if self.client:
            self.client.disconnect()

