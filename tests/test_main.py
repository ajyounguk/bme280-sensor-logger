import json

import pytest

import main
from src.config import parse_config
from src.metoffice import LandObservationsClient, MetOfficePoller
from src.mongo import MongoStore
from src.mqtt_handler import MQTTHandler
from src.sensor import FakeSensor
from tests.conftest import FakeMongoClient, FakeMqttClient, FakeResponse, FakeSession, load_fixture


class Mono:
    t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def app(raw_config, fake_session, mqtt_client_factory):
    cfg = parse_config(raw_config)
    mono = Mono()
    client = LandObservationsClient("k", 51.5, -0.12, session=fake_session)
    a = main.App(
        cfg=cfg,
        sensor=FakeSensor("lounge", seed=3),
        poller=MetOfficePoller(client, "outside", 3600, monotonic=mono),
        mongo=MongoStore(cfg.mongo, client_factory=FakeMongoClient),
        mqtt_factory=lambda c, client_id: MQTTHandler(c, client_id, client_factory=mqtt_client_factory),
    )
    a.mono = mono
    return a


def published(topic):
    return [p for c in FakeMqttClient.instances for (t, p, _) in c.published if t == topic]


def test_full_cycle_publishes_and_stores(app):
    app.run_cycle()
    sensor_msgs = published("homeassistant/bme280_test")
    met_msgs = published("homeassistant/metoffice")
    assert len(sensor_msgs) == 1 and set(sensor_msgs[0]) == {"source", "temperature", "pressure", "humidity", "wind"}
    assert met_msgs[0]["temperature"] == 9.13 and met_msgs[0]["deviceName"] == "test_pi"
    docs = app.mongo.collection.docs
    assert [d["source"] for d in docs] == ["lounge", "outside"]


def test_met_office_called_hourly_but_mqtt_refreshed_every_cycle(app, fake_session):
    for _ in range(6):  # six 10-minute cycles
        app.run_cycle()
        app.mono.t += 600
    assert len(fake_session.calls) == 2  # nearest + one observations fetch
    assert len(published("homeassistant/metoffice")) == 6
    assert sum(d["source"] == "outside" for d in app.mongo.collection.docs) == 1
    assert sum(d["source"] == "lounge" for d in app.mongo.collection.docs) == 6


def test_sensor_failure_does_not_stop_cycle(app, caplog):
    class Broken:
        def read(self):
            raise OSError(121, "Remote I/O error")

    app.sensor = Broken()
    app.run_cycle()
    assert "Sensor read failed" in caplog.text
    assert published("homeassistant/bme280_test") == []
    assert len(published("homeassistant/metoffice")) == 1


def test_mqtt_down_still_writes_mongo(app):
    app.mqtt_factory = lambda c, client_id: MQTTHandler(
        c, client_id, client_factory=lambda **kw: FakeMqttClient(fail_connect=True, **kw)
    )
    app.run_cycle()
    assert len(app.mongo.collection.docs) == 2


def test_run_once_and_stop_event(app):
    app.run(once=True)
    assert len(app.mongo.collection.docs) == 2
    app.stop.set()
    app.run()  # returns immediately
    assert len(app.mongo.collection.docs) == 2


def test_main_once_with_fake_config(capsys):
    from tests.conftest import ROOT

    assert main.main(["--config", str(ROOT / "config" / "config-fake.json"), "--once"]) == 0
    out = capsys.readouterr().out
    assert "BME280 - Temperature" in out
    assert "Stopped." in out


def test_main_bad_config_exits_2(tmp_path, capsys):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"app": {}}), encoding="utf-8")
    assert main.main(["--config", str(p), "--once"]) == 2
    assert "Config error" in capsys.readouterr().out


def test_main_startup_log_masks_secrets(tmp_path, raw_config, capsys, monkeypatch):
    raw_config["metoffice"]["enabled"] = False
    raw_config["mongo"]["enabled"] = False
    raw_config["mqtt"]["mqttPassword"] = "hunter2"
    monkeypatch.setattr(MQTTHandler, "connect", lambda self: False)
    p = tmp_path / "c.json"
    p.write_text(json.dumps(raw_config), encoding="utf-8")
    assert main.main(["--config", str(p), "--once"]) == 0
    out = capsys.readouterr().out
    assert "hunter2" not in out
    assert "MQTT password: ****" in out


def test_met_office_unavailable_at_startup_recovers(raw_config, mqtt_client_factory):
    cfg = parse_config(raw_config)
    s = FakeSession({"nearest": FakeResponse(503, {})})
    mono = Mono()
    a = main.App(
        cfg=cfg,
        sensor=FakeSensor("lounge", seed=1),
        poller=MetOfficePoller(LandObservationsClient("k", 51.5, -0.12, session=s), "outside", 3600, monotonic=mono),
        mqtt_factory=lambda c, client_id: MQTTHandler(c, client_id, client_factory=mqtt_client_factory),
    )
    a.run_cycle()
    assert published("homeassistant/metoffice") == []
    s.routes = {
        "nearest": FakeResponse(200, load_fixture("nearest.json")),
        "*": FakeResponse(200, load_fixture("observations.json")),
    }
    mono.t += MetOfficePoller.RETRY_AFTER_FAILURE
    a.run_cycle()
    assert published("homeassistant/metoffice")[0]["temperature"] == 9.13
