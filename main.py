"""bme280-sensor-logger

Reads temperature, pressure and humidity from a BME280 (or a fake sensor for development), optionally fetches
outdoor observations from the Met Office Weather DataHub, and publishes both to MQTT (e.g. Home Assistant) and/or
MongoDB.

Usage:
    python main.py                        # run forever, config from config/config.json
    python main.py --config path.json     # another config file
    python main.py --once                 # one cycle, then exit (handy for checking a setup)
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from dataclasses import dataclass, field

from src.config import Config, ConfigError, load_config
from src.metoffice import LandObservationsClient, MetOfficePoller
from src.mongo import MongoStore
from src.mqtt_handler import MQTTHandler
from src.sensor import Sensor, build_sensor

log = logging.getLogger("bme280-logger")

DEFAULT_CONFIG = "config/config.json"


def setup_logging(level: str = "INFO") -> None:
    # Windows consoles default to a legacy code page; keep "°C" readable.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=level,
        format="[%(levelname)s %(asctime)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # Library chatter (urllib3 connection pool, pymongo topology) stays out unless debugging.
    for noisy in ("urllib3", "pymongo"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, logging.getLogger().level))


@dataclass
class App:
    cfg: Config
    sensor: Sensor
    poller: MetOfficePoller | None = None
    mongo: MongoStore | None = None
    mqtt_factory: type = MQTTHandler
    stop: threading.Event = field(default_factory=threading.Event)

    @classmethod
    def from_config(cls, cfg: Config) -> App:
        poller = None
        if cfg.metoffice.enabled:
            client = LandObservationsClient(
                cfg.metoffice.api_key, cfg.metoffice.latitude, cfg.metoffice.longitude, cfg.metoffice.geohash
            )
            poller = MetOfficePoller(client, cfg.metoffice.source, cfg.metoffice.poll_interval)
        mongo = MongoStore(cfg.mongo) if cfg.mongo.enabled else None
        return cls(cfg=cfg, sensor=build_sensor(cfg.sensor), poller=poller, mongo=mongo)

    def run_cycle(self) -> None:
        cfg = self.cfg
        mqtt = None
        if cfg.mqtt.enabled:
            mqtt = self.mqtt_factory(cfg.mqtt, client_id=f"bme280-logger-{cfg.app.device_name}")
            mqtt.connect()
        try:
            try:
                reading = self.sensor.read()
            except Exception as e:  # noqa: BLE001 - I2C errors are OSError, but keep the loop alive whatever happens
                log.error("Sensor read failed: %s", e)
                reading = None

            if reading:
                log.info(
                    "BME280 - Temperature: %s °C, Pressure: %s hPa, Humidity: %s %%",
                    reading["temperature"],
                    reading["pressure"],
                    reading["humidity"],
                )
                if mqtt:
                    mqtt.publish(cfg.mqtt.sensor_topic, reading)
                if self.mongo:
                    self.mongo.insert(reading, cfg.app.device_name)

            if self.poller:
                # The API is called at most once per poll interval; new observations go to Mongo once,
                # while MQTT gets the latest one every cycle so Home Assistant recovers quickly after a restart.
                new = self.poller.poll()
                if new:
                    log.info(
                        "MetOffice - Temperature: %s °C, Humidity: %s %%, Pressure: %s hPa, Wind: %s m/s (observed %s)",
                        new["temperature"],
                        new["humidity"],
                        new["pressure"],
                        new["wind"],
                        new["observedAt"],
                    )
                    if self.mongo and not self.mongo.observation_exists(new["source"], new["observedAt"]):
                        self.mongo.insert(new, cfg.app.device_name)
                latest = self.poller.last_reading
                if mqtt and latest:
                    mqtt.publish(cfg.mqtt.metoffice_topic, {**latest, "deviceName": cfg.app.device_name})
        finally:
            if mqtt:
                mqtt.disconnect()

    def run(self, once: bool = False) -> None:
        while not self.stop.is_set():
            self.run_cycle()
            if once:
                break
            self.stop.wait(self.cfg.app.reading_interval)

    def close(self) -> None:
        if self.mongo:
            self.mongo.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BME280 + Met Office logger for MQTT and MongoDB")
    p.add_argument("--config", default=DEFAULT_CONFIG, help=f"config file (default: {DEFAULT_CONFIG})")
    p.add_argument("--once", action="store_true", help="run one cycle and exit")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging()
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        log.error("Config error: %s", e)
        return 2
    setup_logging(cfg.app.log_level)

    log.info("bme280-sensor-logger starting...")
    for line in cfg.summary():
        log.info("%s", line)

    try:
        app = App.from_config(cfg)
    except ImportError as e:
        log.error('Sensor libraries not available (%s). Install requirements, or set sensor.type to "fake".', e)
        return 2

    def _stop(signum, _frame):
        log.info("Received %s, stopping...", signal.Signals(signum).name)
        app.stop.set()

    signal.signal(signal.SIGTERM, _stop)  # pm2 / systemd stop
    try:
        app.run(once=args.once)
    except KeyboardInterrupt:
        log.info("Program stopped by user.")
    finally:
        app.close()
        log.info("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
