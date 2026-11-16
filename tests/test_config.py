import json

import pytest

from src.config import ConfigError, load_config, mask_uri, parse_config


def test_valid_config_parses(raw_config):
    cfg = parse_config(raw_config)
    assert cfg.app.reading_interval == 600
    assert cfg.sensor.type == "fake"
    assert cfg.sensor.address == 0x76
    assert cfg.sensor.source == "lounge"
    assert cfg.metoffice.latitude == 51.5
    assert cfg.metoffice.source == "outside"
    assert cfg.mqtt.port == 1883


def test_example_configs_shipped_in_repo_are_valid_shape():
    from tests.conftest import ROOT

    fake = load_config(ROOT / "config" / "config-fake.json")
    assert fake.sensor.type == "fake"
    assert not (fake.mqtt.enabled or fake.mongo.enabled or fake.metoffice.enabled)

    # The example deliberately has placeholders, so it must be rejected until edited.
    with pytest.raises(ConfigError, match="placeholder"):
        load_config(ROOT / "config" / "config-example.json")


def test_summary_masks_secrets(raw_config):
    text = "\n".join(parse_config(raw_config).summary())
    assert "test-key-123" not in text
    assert "mqtt-pass" not in text
    assert "s3cret" not in text
    assert "****" in text


def test_mask_uri():
    assert mask_uri("mongodb+srv://u:p@h/db") == "mongodb+srv://u:****@h/db"
    assert mask_uri("mongodb://h:27017/db") == "mongodb://h:27017/db"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda c: c.pop("mqtt"), "'mqtt' section"),
        (lambda c: c["app"].update(readingIntervalSeconds="600"), "must be a number"),
        (lambda c: c["app"].update(readingIntervalSeconds=True), "got a boolean"),
        (lambda c: c["app"].update(readingIntervalSeconds=1), "between"),
        (lambda c: c["app"].update(logLevel="LOUD"), "logLevel"),
        (lambda c: c["sensor"].update(type="dht22"), "sensor.type"),
        (lambda c: c["sensor"].update(bme280_address="0xZZ"), "hex string"),
        (lambda c: c["sensor"].update(bme280_address="0x99"), "between"),
        (lambda c: c["metoffice"].update(APIKey="YOUR_METOFFICE_API_KEY"), "placeholder"),
        (lambda c: c["metoffice"].update(APIKey=""), "must not be empty"),
        (lambda c: c["metoffice"].pop("latitude"), "latitude"),
        (lambda c: c["metoffice"].update(latitude=95), "between"),
        (lambda c: c["metoffice"].update(pollIntervalSeconds=60), "free plan"),
        (lambda c: c["metoffice"].update(geohash="ai!"), "geohash"),
        (lambda c: c["mongo"].update(uri="http://nope"), "mongodb://"),
        (lambda c: c["mongo"].update(uri="mongodb+srv://MONGO_USERNAME:MONGO_PASSWORD@x/"), "placeholder"),
        (lambda c: c["mqtt"].update(port=70000), "between"),
        (lambda c: c["mqtt"].update(mqttPassword="YOUR_MQTT_PASSWORD"), "placeholder"),
        (lambda c: c["mqtt"].update(enabled="yes"), "true/false"),
    ],
)
def test_invalid_config_rejected(raw_config, mutate, message):
    mutate(raw_config)
    with pytest.raises(ConfigError, match=message):
        parse_config(raw_config)


def test_old_datapoint_location_id_gets_migration_hint(raw_config):
    met = raw_config["metoffice"]
    met.pop("latitude")
    met.pop("longitude")
    met["locationID"] = "1234"
    with pytest.raises(ConfigError, match="DataPoint"):
        parse_config(raw_config)


def test_geohash_override_removes_need_for_lat_lon(raw_config):
    met = raw_config["metoffice"]
    met.pop("latitude")
    met.pop("longitude")
    met["geohash"] = "GCPVJ0"
    assert parse_config(raw_config).metoffice.geohash == "gcpvj0"


def test_disabled_sections_need_no_details(raw_config):
    raw_config["metoffice"] = {"enabled": False}
    raw_config["mongo"] = {"enabled": False}
    raw_config["mqtt"] = {"enabled": False}
    cfg = parse_config(raw_config)
    assert cfg.sensor.source == "bme280"  # default when mongo section has no sensorSource
    assert not cfg.metoffice.enabled


def test_load_config_errors(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_config(bad)


def test_load_config_from_file(tmp_path, raw_config):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(raw_config), encoding="utf-8")
    assert load_config(p).app.device_name == "test_pi"
