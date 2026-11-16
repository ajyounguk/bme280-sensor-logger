"""Met Office Weather DataHub - Land Observations API.

Replaces the retired DataPoint `wxobs` feed with its DataHub equivalent: hourly *observations* (not forecasts)
from the nearest of ~150 UK stations.

Flow:
  GET {BASE_URL}/nearest?lat=..&lon=..  -> [{"geohash": "gcpvj0", "area": ..., ...}]   (once; cached)
  GET {BASE_URL}/{geohash}              -> [{"datetime": "...Z", "temperature": .., "humidity": ..,
                                             "mslp": .., "wind_speed": .., ...}, ...]  (last 48 h, hourly)
Auth: `apikey` header. Free plan: 360 calls/day, reset 00:00 UTC; over quota returns HTTP 429.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from src.config import DATAHUB_DAILY_LIMIT

log = logging.getLogger(__name__)

BASE_URL = "https://data.hub.api.metoffice.gov.uk/observation-land/1"
# Our own hard stop, below the plan limit, in case of restarts or a mis-set interval.
DAILY_CALL_BUDGET = DATAHUB_DAILY_LIMIT - 20


class MetOfficeError(Exception):
    """The Met Office API call failed or returned something unusable."""


class QuotaExceeded(MetOfficeError):
    """Daily quota used up (HTTP 429 or our own budget). Calls are suspended until 00:00 UTC."""


def _next_utc_midnight(now: datetime) -> datetime:
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _number(obs: dict, key: str) -> float | None:
    value = obs.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_observations(data: Any, source: str) -> dict | None:
    """Return the latest observation that has a temperature, in the app's payload shape, or None."""
    if not isinstance(data, list):
        raise MetOfficeError(f"unexpected observations response type: {type(data).__name__}")

    usable = [o for o in data if isinstance(o, dict) and _number(o, "temperature") is not None and o.get("datetime")]
    if not usable:
        return None
    latest = max(usable, key=lambda o: str(o["datetime"]))  # ISO-8601 UTC strings sort chronologically

    pressure = _number(latest, "mslp")
    if pressure is not None and pressure > 2000:  # guard: Pa rather than hPa
        pressure /= 100
    humidity = _number(latest, "humidity")
    wind = _number(latest, "wind_speed")  # m/s

    return {
        "source": source,
        "temperature": round(_number(latest, "temperature"), 2),
        "humidity": round(humidity, 2) if humidity is not None else None,
        "pressure": round(pressure, 2) if pressure is not None else None,
        "wind": round(wind, 2) if wind is not None else None,
        "observedAt": latest["datetime"],
    }


class LandObservationsClient:
    def __init__(
        self,
        api_key: str,
        latitude: float | None = None,
        longitude: float | None = None,
        geohash: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 15,
        clock=lambda: datetime.now(UTC),
    ):
        self._session = session or requests.Session()
        self._session.headers.update({"apikey": api_key, "accept": "application/json"})
        self.latitude = latitude
        self.longitude = longitude
        self.geohash = geohash
        self.timeout = timeout
        self._clock = clock
        self._day = None
        self._calls_today = 0
        self._suspended_until: datetime | None = None

    # -- quota bookkeeping ----------------------------------------------------------------------------------

    @property
    def calls_today(self) -> int:
        return self._calls_today

    def _check_budget(self) -> None:
        now = self._clock()
        if self._day != now.date():
            self._day, self._calls_today = now.date(), 0
        if self._suspended_until and now < self._suspended_until:
            raise QuotaExceeded(f"Met Office quota exhausted; calls suspended until {self._suspended_until:%H:%M} UTC")
        self._suspended_until = None
        if self._calls_today >= DAILY_CALL_BUDGET:
            self._suspended_until = _next_utc_midnight(now)
            raise QuotaExceeded(f"local daily budget of {DAILY_CALL_BUDGET} calls used; resuming at 00:00 UTC")

    def _get(self, path: str, params: dict | None = None) -> Any:
        self._check_budget()
        self._calls_today += 1
        url = f"{BASE_URL}/{path.lstrip('/')}"
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise MetOfficeError(f"request failed: {type(e).__name__}") from e
        if resp.status_code == 429:
            self._suspended_until = _next_utc_midnight(self._clock())
            raise QuotaExceeded("Met Office returned HTTP 429 (daily quota); resuming at 00:00 UTC")
        if resp.status_code in (401, 403):
            raise MetOfficeError(
                f"HTTP {resp.status_code}: API key rejected - check it is a Land Observations subscription key"
            )
        if not resp.ok:
            raise MetOfficeError(f"HTTP {resp.status_code} from {path.split('?')[0]}")
        try:
            return resp.json()
        except ValueError as e:
            raise MetOfficeError("response was not valid JSON") from e

    # -- API ------------------------------------------------------------------------------------------------

    def resolve_geohash(self) -> str:
        """Nearest observation station's geohash for the configured lat/lon. Cached after the first call."""
        if self.geohash:
            return self.geohash
        data = self._get("nearest", {"lat": round(self.latitude, 2), "lon": round(self.longitude, 2)})
        first = data[0] if isinstance(data, list) and data else data
        geohash = first.get("geohash") if isinstance(first, dict) else None
        if not geohash:
            raise MetOfficeError("nearest-station lookup returned no geohash")
        self.geohash = geohash
        log.info("Met Office nearest station: %s (%s)", geohash, first.get("area", "unknown area"))
        return geohash

    def latest(self, source: str) -> dict | None:
        geohash = self.resolve_geohash()
        return parse_observations(self._get(geohash), source)


class MetOfficePoller:
    """Calls the API at most once per poll interval (sooner after a transient failure)."""

    RETRY_AFTER_FAILURE = 600  # seconds; still far inside the free-plan quota

    def __init__(self, client: LandObservationsClient, source: str, poll_interval: int, monotonic=time.monotonic):
        self.client = client
        self.source = source
        self.poll_interval = poll_interval
        self._monotonic = monotonic
        self._next_due: float | None = None
        self.last_observed_at: str | None = None
        self.last_reading: dict | None = None

    def due(self) -> bool:
        return self._next_due is None or self._monotonic() >= self._next_due

    def poll(self) -> dict | None:
        """Return a reading if a *new* observation was fetched this call, else None."""
        if not self.due():
            return None
        now = self._monotonic()
        self._next_due = now + self.poll_interval
        try:
            reading = self.client.latest(self.source)
        except QuotaExceeded as e:
            log.warning("%s", e)
            return None
        except MetOfficeError as e:
            log.error("Met Office fetch failed: %s", e)
            self._next_due = now + min(self.poll_interval, self.RETRY_AFTER_FAILURE)
            return None
        if reading is None:
            log.warning("Met Office returned no usable observation")
            return None
        if reading["observedAt"] == self.last_observed_at:
            log.debug("Met Office observation unchanged (%s)", reading["observedAt"])
            return None
        self.last_observed_at = reading["observedAt"]
        self.last_reading = reading
        return reading
