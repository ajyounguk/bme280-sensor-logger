"""MongoDB persistence. One long-lived client per process (pymongo pools connections internally)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from src.config import MongoConfig

log = logging.getLogger(__name__)


class MongoStore:
    def __init__(self, cfg: MongoConfig, client_factory=MongoClient):
        self._cfg = cfg
        self._client_factory = client_factory
        self._client = None

    @property
    def collection(self):
        if self._client is None:
            self._client = self._client_factory(self._cfg.uri, serverSelectionTimeoutMS=10_000, tz_aware=True)
        return self._client[self._cfg.db_name][self._cfg.collection]

    def insert(self, reading: dict, device_name: str) -> bool:
        """Insert a reading. Field order matches the original documents so existing charts keep working."""
        doc = {
            "source": reading.get("source"),
            "timestamp": datetime.now(UTC),
            "temperature": reading.get("temperature"),
            "pressure": reading.get("pressure"),
            "humidity": reading.get("humidity"),
            "wind": reading.get("wind"),
            "deviceName": device_name,
        }
        if reading.get("observedAt"):
            doc["observedAt"] = reading["observedAt"]
        try:
            self.collection.insert_one(doc)
            return True
        except PyMongoError as e:
            log.error("MongoDB insert failed: %s", type(e).__name__)
            log.debug("MongoDB insert error detail", exc_info=True)
            return False

    def observation_exists(self, source: str, observed_at: str) -> bool:
        """True if this Met Office observation is already stored (e.g. by another device sharing the collection).

        On a database error, return True: skipping one hourly observation beats writing duplicates.
        """
        try:
            return self.collection.find_one({"source": source, "observedAt": observed_at}, {"_id": 1}) is not None
        except PyMongoError as e:
            log.error("MongoDB lookup failed: %s", type(e).__name__)
            return True

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
