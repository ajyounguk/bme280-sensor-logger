"""Load and validate config/config.json.

Validation is deliberately strict: the app runs unattended under pm2, so a typo should stop it at start-up
with a clear message rather than fail hours later inside the loop.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Met Office Weather DataHub free plan: 360 calls per day, reset at 00:00 UTC.
DATAHUB_DAILY_LIMIT = 360
# 300 s => at most 288 observation calls/day, leaving headroom for the one-off "nearest" lookup and restarts.
MIN_METOFFICE_POLL_SECONDS = 300
MIN_READING_INTERVAL_SECONDS = 5

SENSOR_TYPES = ("bme280", "fake")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
_GEOHASH_RE = re.compile(r"^[0-9b-hjkmnp-z]{1,12}$")
_PLACEHOLDER_RE = re.compile(r"^(YOUR_|CHANGE_ME)", re.IGNORECASE)


class ConfigError(ValueError):
    """Raised when the configuration file is missing or invalid."""


@dataclass(frozen=True)
class AppConfig:
    reading_interval: int
    device_name: str
    log_level: str


@dataclass(frozen=True)
class SensorConfig:
    type: str
    i2c_port: int
    address: int
    source: str


@dataclass(frozen=True)
class MetOfficeConfig:
    enabled: bool
    api_key: str
    latitude: float | None
    longitude: float | None
    geohash: str | None
    poll_interval: int
    source: str


@dataclass(frozen=True)
class MongoConfig:
    enabled: bool
    uri: str
    db_name: str
    collection: str


@dataclass(frozen=True)
class MqttConfig:
    enabled: bool
    broker: str
    port: int
    username: str
    password: str
    sensor_topic: str
    metoffice_topic: str


@dataclass(frozen=True)
class Config:
    app: AppConfig
    sensor: SensorConfig
    metoffice: MetOfficeConfig
    mongo: MongoConfig
    mqtt: MqttConfig

    def summary(self) -> list[str]:
        """Human-readable config lines with secrets masked, for the start-up log."""
        lines = [
            f"Device name: {self.app.device_name}",
            f"Reading interval: {self.app.reading_interval} s",
            f"Sensor: {self.sensor.type} (I2C port {self.sensor.i2c_port}, address {hex(self.sensor.address)})",
            f"MongoDB enabled: {self.mongo.enabled}",
        ]
        if self.mongo.enabled:
            lines += [
                f"MongoDB URI: {mask_uri(self.mongo.uri)}",
                f"MongoDB database/collection: {self.mongo.db_name}/{self.mongo.collection}",
            ]
        lines.append(f"Met Office enabled: {self.metoffice.enabled}")
        if self.metoffice.enabled:
            where = (
                f"geohash {self.metoffice.geohash}"
                if self.metoffice.geohash
                else f"lat {self.metoffice.latitude}, lon {self.metoffice.longitude}"
            )
            lines += [
                f"Met Office location: {where}",
                f"Met Office poll interval: {self.metoffice.poll_interval} s",
                f"Met Office API key: {mask_secret(self.metoffice.api_key)}",
            ]
        lines.append(f"MQTT enabled: {self.mqtt.enabled}")
        if self.mqtt.enabled:
            lines += [
                f"MQTT broker: {self.mqtt.broker}:{self.mqtt.port}",
                f"MQTT username: {self.mqtt.username or '(none)'}",
                f"MQTT password: {mask_secret(self.mqtt.password)}",
                f"MQTT topics: {self.mqtt.sensor_topic}, {self.mqtt.metoffice_topic}",
            ]
        return lines


def mask_secret(value: str) -> str:
    return "(not set)" if not value else "****"


def mask_uri(uri: str) -> str:
    """Hide the password in a mongodb:// or mongodb+srv:// URI."""
    return re.sub(r"(://[^:/@]+:)[^@]+@", r"\1****@", uri)


# --- helpers -------------------------------------------------------------------------------------------------


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"'{name}' section is missing or not an object")
    return value


_MISSING = object()


def _get(section: dict[str, Any], path: str, key: str, kind: type | tuple[type, ...], default: Any = _MISSING) -> Any:
    if key not in section or section[key] is None:
        if default is _MISSING:
            raise ConfigError(f"'{path}.{key}' is required")
        return default
    value = section[key]
    # bool is a subclass of int: don't accept true/false where a number is expected.
    if isinstance(value, bool) and bool not in (kind if isinstance(kind, tuple) else (kind,)):
        raise ConfigError(f"'{path}.{key}' must be {_kind_name(kind)}, got a boolean")
    if not isinstance(value, kind):
        raise ConfigError(f"'{path}.{key}' must be {_kind_name(kind)}, got {type(value).__name__}")
    return value


def _kind_name(kind: type | tuple[type, ...]) -> str:
    kinds = kind if isinstance(kind, tuple) else (kind,)
    names = {bool: "true/false", int: "a number", float: "a number", str: "a string"}
    return " or ".join(dict.fromkeys(names.get(k, k.__name__) for k in kinds))


def _non_empty(value: str, name: str) -> str:
    value = value.strip()
    if not value:
        raise ConfigError(f"'{name}' must not be empty")
    return value


def _not_placeholder(value: str, name: str) -> str:
    if _PLACEHOLDER_RE.match(value):
        raise ConfigError(f"'{name}' still has the placeholder value from config-example.json")
    return value


def _in_range(value: float, lo: float, hi: float, name: str) -> float:
    if not lo <= value <= hi:
        raise ConfigError(f"'{name}' must be between {lo} and {hi}, got {value}")
    return value


# --- parsing -------------------------------------------------------------------------------------------------


def parse_config(raw: Any) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a JSON object")

    # app
    s = _section(raw, "app")
    reading_interval = _in_range(
        _get(s, "app", "readingIntervalSeconds", int), MIN_READING_INTERVAL_SECONDS, 86400, "app.readingIntervalSeconds"
    )
    app = AppConfig(
        reading_interval=int(reading_interval),
        device_name=_non_empty(_get(s, "app", "deviceName", str), "app.deviceName"),
        log_level=_get(s, "app", "logLevel", str, "INFO").upper(),
    )
    if app.log_level not in LOG_LEVELS:
        raise ConfigError(f"'app.logLevel' must be one of {', '.join(LOG_LEVELS)}")

    # mongo (also carries the "source" labels, kept there for backwards compatibility)
    m = _section(raw, "mongo")
    mongo_enabled = _get(m, "mongo", "enabled", bool)
    sensor_source = _non_empty(_get(m, "mongo", "sensorSource", str, "bme280"), "mongo.sensorSource")
    metoffice_source = _non_empty(_get(m, "mongo", "metofficeSource", str, "metoffice"), "mongo.metofficeSource")
    if mongo_enabled:
        uri = _non_empty(_get(m, "mongo", "uri", str), "mongo.uri")
        if not uri.startswith(("mongodb://", "mongodb+srv://")):
            raise ConfigError("'mongo.uri' must start with mongodb:// or mongodb+srv://")
        if "MONGO_PASSWORD" in uri or "MONGO_USERNAME" in uri:
            raise ConfigError("'mongo.uri' still has the placeholder credentials from config-example.json")
        mongo = MongoConfig(
            enabled=True,
            uri=uri,
            db_name=_not_placeholder(_non_empty(_get(m, "mongo", "dbName", str), "mongo.dbName"), "mongo.dbName"),
            collection=_non_empty(_get(m, "mongo", "collection", str), "mongo.collection"),
        )
    else:
        mongo = MongoConfig(False, "", "", "")

    # sensor
    s = _section(raw, "sensor")
    sensor_type = _get(s, "sensor", "type", str, "bme280").lower()
    if sensor_type not in SENSOR_TYPES:
        raise ConfigError(f"'sensor.type' must be one of {', '.join(SENSOR_TYPES)}")
    address_raw = _get(s, "sensor", "bme280_address", (str, int), "0x76")
    try:
        address = int(address_raw, 16) if isinstance(address_raw, str) else address_raw
    except ValueError:
        raise ConfigError(f"'sensor.bme280_address' must be a hex string like \"0x76\", got {address_raw!r}") from None
    sensor = SensorConfig(
        type=sensor_type,
        i2c_port=int(_in_range(_get(s, "sensor", "i2c_port", int, 1), 0, 20, "sensor.i2c_port")),
        address=int(_in_range(address, 0x03, 0x77, "sensor.bme280_address")),
        source=sensor_source,
    )

    # metoffice
    s = _section(raw, "metoffice")
    met_enabled = _get(s, "metoffice", "enabled", bool)
    if met_enabled:
        if "locationID" in s and "latitude" not in s and "geohash" not in s:
            raise ConfigError(
                "'metoffice.locationID' was for the retired DataPoint API. "
                "Replace it with 'latitude' and 'longitude' (see config-example.json and README)"
            )
        api_key = _not_placeholder(
            _non_empty(_get(s, "metoffice", "APIKey", str), "metoffice.APIKey"), "metoffice.APIKey"
        )
        geohash = _get(s, "metoffice", "geohash", str, "").strip().lower() or None
        if geohash and not _GEOHASH_RE.match(geohash):
            raise ConfigError(f"'metoffice.geohash' is not a valid geohash: {geohash!r}")
        lat = _get(s, "metoffice", "latitude", (int, float), None)
        lon = _get(s, "metoffice", "longitude", (int, float), None)
        if geohash is None and (lat is None or lon is None):
            raise ConfigError(
                "'metoffice.latitude' and 'metoffice.longitude' are required (or set 'metoffice.geohash')"
            )
        if lat is not None:
            _in_range(lat, -90, 90, "metoffice.latitude")
        if lon is not None:
            _in_range(lon, -180, 180, "metoffice.longitude")
        poll = _get(s, "metoffice", "pollIntervalSeconds", int, 3600)
        if poll < MIN_METOFFICE_POLL_SECONDS:
            raise ConfigError(
                f"'metoffice.pollIntervalSeconds' must be at least {MIN_METOFFICE_POLL_SECONDS} "
                f"to stay inside the DataHub free plan ({DATAHUB_DAILY_LIMIT} calls/day)"
            )
        metoffice = MetOfficeConfig(
            enabled=True,
            api_key=api_key,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            geohash=geohash,
            poll_interval=poll,
            source=metoffice_source,
        )
    else:
        metoffice = MetOfficeConfig(False, "", None, None, None, 3600, metoffice_source)

    # mqtt
    s = _section(raw, "mqtt")
    mqtt_enabled = _get(s, "mqtt", "enabled", bool)
    if mqtt_enabled:
        username = _get(s, "mqtt", "mqttUsername", str, "")
        password = _get(s, "mqtt", "mqttPassword", str, "")
        _not_placeholder(username, "mqtt.mqttUsername")
        _not_placeholder(password, "mqtt.mqttPassword")
        mqtt = MqttConfig(
            enabled=True,
            broker=_non_empty(_get(s, "mqtt", "broker", str), "mqtt.broker"),
            port=int(_in_range(_get(s, "mqtt", "port", int, 1883), 1, 65535, "mqtt.port")),
            username=username,
            password=password,
            sensor_topic=_non_empty(_get(s, "mqtt", "sensorTopic", str), "mqtt.sensorTopic"),
            metoffice_topic=_non_empty(_get(s, "mqtt", "metofficeTopic", str), "mqtt.metofficeTopic"),
        )
    else:
        mqtt = MqttConfig(False, "", 1883, "", "", "", "")

    return Config(app=app, sensor=sensor, metoffice=metoffice, mongo=mongo, mqtt=mqtt)


def load_config(path: str | Path) -> Config:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path} (copy config/config-example.json to get started)") from None
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} is not valid JSON: line {e.lineno} column {e.colno}: {e.msg}") from None
    return parse_config(raw)
