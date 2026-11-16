import paho.mqtt.client as mqtt

from src.config import MqttConfig
from src.mqtt_handler import MQTTHandler

CFG = MqttConfig(True, "broker.test", 1884, "logger", "pw", "t/sensor", "t/met")


def test_connect_publish_disconnect(mqtt_client_factory):
    with MQTTHandler(CFG, "id-1", client_factory=mqtt_client_factory) as h:
        assert h.publish("t/sensor", {"temperature": 20.5})
        client = mqtt_client_factory.instances[0]
        assert client.connected_to == ("broker.test", 1884)
        assert client.loop_running
    assert client.callback_api_version == mqtt.CallbackAPIVersion.VERSION2
    assert client.client_id == "id-1"
    assert client.credentials == ("logger", "pw")
    assert client.published == [("t/sensor", {"temperature": 20.5}, 1)]
    assert not client.loop_running
    assert h.client is None


def test_no_credentials_when_username_blank(mqtt_client_factory):
    cfg = MqttConfig(True, "b", 1883, "", "", "a", "b")
    with MQTTHandler(cfg, "id", client_factory=mqtt_client_factory):
        pass
    assert mqtt_client_factory.instances[0].credentials is None


def test_connect_failure_is_logged_and_publish_is_noop(caplog):
    def factory(**kw):
        from tests.conftest import FakeMqttClient

        return FakeMqttClient(fail_connect=True, **kw)

    h = MQTTHandler(CFG, "id", client_factory=factory)
    assert h.connect() is False
    assert h.publish("t", {"a": 1}) is False
    h.disconnect()
    assert "Failed to connect" in caplog.text
    assert "pw" not in caplog.text


def test_broker_refusal_reported(caplog):
    from tests.conftest import FakeMqttClient, FakeReasonCode

    clients = []

    def factory(**kw):
        c = FakeMqttClient(connack=FakeReasonCode(failure=True, text="Not authorized"), **kw)
        clients.append(c)
        return c

    h = MQTTHandler(CFG, "id", client_factory=factory)
    assert h.connect() is False
    assert "Not authorized" in caplog.text
    assert not clients[0].loop_running


def test_no_connack_times_out(caplog, monkeypatch):
    from src import mqtt_handler
    from tests.conftest import FakeMqttClient

    monkeypatch.setattr(mqtt_handler, "CONNECT_TIMEOUT", 0.01)
    h = MQTTHandler(CFG, "id", client_factory=lambda **kw: FakeMqttClient(connack=None, **kw))
    assert h.connect() is False
    assert "no CONNACK" in caplog.text


def test_unconfirmed_publish_reported(caplog):
    def factory(**kw):
        from tests.conftest import FakeMqttClient

        return FakeMqttClient(publish_ok=False, **kw)

    with MQTTHandler(CFG, "id", client_factory=factory) as h:
        assert h.publish("t", {"a": 1}) is False
    assert "not confirmed" in caplog.text
