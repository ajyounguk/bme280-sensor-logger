from datetime import UTC, datetime

import pytest
import requests

from src.metoffice import (
    BASE_URL,
    DAILY_CALL_BUDGET,
    LandObservationsClient,
    MetOfficeError,
    MetOfficePoller,
    QuotaExceeded,
    parse_observations,
)
from tests.conftest import FakeResponse, FakeSession, load_fixture


class Clock:
    def __init__(self, dt):
        self.now = dt

    def __call__(self):
        return self.now


def make_client(session, **kw):
    return LandObservationsClient("k3y", latitude=51.5012, longitude=-0.1234, session=session, **kw)


# --- parsing -------------------------------------------------------------------------------------------------


def test_parse_picks_latest_observation_with_temperature():
    r = parse_observations(load_fixture("observations.json"), "outside")
    # 11:00 has no temperature, so 10:00 wins even though it is listed last
    assert r == {
        "source": "outside",
        "temperature": 9.13,
        "humidity": 85.0,
        "pressure": 1025.0,
        "wind": 1.4,
        "observedAt": "2026-11-16T10:00:00Z",
    }


def test_parse_converts_pascals_and_tolerates_missing_fields():
    r = parse_observations([{"datetime": "2026-11-16T10:00:00Z", "temperature": "7.5", "mslp": 101320}], "o")
    assert r["temperature"] == 7.5
    assert r["pressure"] == 1013.2
    assert r["humidity"] is None and r["wind"] is None


def test_parse_empty_or_unusable_returns_none():
    assert parse_observations([], "o") is None
    assert parse_observations([{"datetime": "x", "temperature": None}], "o") is None


def test_parse_rejects_wrong_shape():
    with pytest.raises(MetOfficeError):
        parse_observations({"SiteRep": {}}, "o")


# --- client --------------------------------------------------------------------------------------------------


def test_client_resolves_nearest_once_then_fetches(fake_session):
    c = make_client(fake_session)
    assert c.latest("outside")["temperature"] == 9.13
    assert c.latest("outside")["temperature"] == 9.13
    urls = [u for u, _ in fake_session.calls]
    assert urls == [f"{BASE_URL}/nearest", f"{BASE_URL}/gcpvj0", f"{BASE_URL}/gcpvj0"]
    assert fake_session.calls[0][1] == {"lat": 51.5, "lon": -0.12}
    assert fake_session.headers["apikey"] == "k3y"


def test_api_key_never_in_url(fake_session):
    make_client(fake_session).latest("o")
    assert all("k3y" not in u and "k3y" not in str(p) for u, p in fake_session.calls)


def test_configured_geohash_skips_nearest_lookup(fake_session):
    c = LandObservationsClient("k", geohash="gcqr9c", session=fake_session)
    c.latest("o")
    assert [u for u, _ in fake_session.calls] == [f"{BASE_URL}/gcqr9c"]


def test_nearest_without_geohash_is_an_error():
    s = FakeSession({"nearest": FakeResponse(200, [])})
    with pytest.raises(MetOfficeError, match="no geohash"):
        make_client(s).latest("o")


@pytest.mark.parametrize(
    "response, match",
    [
        (FakeResponse(401, {}), "API key rejected"),
        (FakeResponse(500, {}), "HTTP 500"),
        (FakeResponse(200, text="<html>"), "not valid JSON"),
        (requests.ConnectionError("boom"), "request failed"),
    ],
)
def test_client_errors(response, match):
    s = FakeSession({"nearest": FakeResponse(200, load_fixture("nearest.json")), "*": response})
    with pytest.raises(MetOfficeError, match=match):
        make_client(s).latest("o")


def test_429_suspends_calls_until_utc_midnight():
    clock = Clock(datetime(2026, 11, 16, 15, 0, tzinfo=UTC))
    s = FakeSession({"nearest": FakeResponse(200, load_fixture("nearest.json")), "*": FakeResponse(429, {})})
    c = make_client(s, clock=clock)
    with pytest.raises(QuotaExceeded):
        c.latest("o")
    calls = len(s.calls)
    with pytest.raises(QuotaExceeded, match="suspended"):
        c.latest("o")
    assert len(s.calls) == calls  # no request made while suspended

    s.routes["*"] = FakeResponse(200, load_fixture("observations.json"))
    clock.now = datetime(2026, 11, 17, 0, 1, tzinfo=UTC)
    assert c.latest("o")["temperature"] == 9.13


def test_local_daily_budget_stops_calls(fake_session):
    clock = Clock(datetime(2026, 11, 16, 1, 0, tzinfo=UTC))
    c = make_client(fake_session, clock=clock)
    c.resolve_geohash()
    for _ in range(DAILY_CALL_BUDGET - 1):
        c.latest("o")
    assert c.calls_today == DAILY_CALL_BUDGET
    with pytest.raises(QuotaExceeded, match="budget"):
        c.latest("o")
    clock.now = datetime(2026, 11, 17, 0, 0, 1, tzinfo=UTC)
    c.latest("o")
    assert c.calls_today == 1


# --- poller --------------------------------------------------------------------------------------------------


class Mono:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_poller_respects_interval_and_dedupes(fake_session):
    mono = Mono()
    p = MetOfficePoller(make_client(fake_session), "outside", poll_interval=3600, monotonic=mono)
    assert p.poll()["observedAt"] == "2026-11-16T10:00:00Z"
    mono.t += 600
    assert p.poll() is None  # not due: no API call
    assert len(fake_session.calls) == 2  # nearest + one observation fetch
    mono.t += 3000
    assert p.poll() is None  # due, fetched, but same observation as before
    assert len(fake_session.calls) == 3
    assert p.last_reading["temperature"] == 9.13


def test_poller_retries_sooner_after_failure(caplog):
    mono = Mono()
    s = FakeSession({"nearest": FakeResponse(200, load_fixture("nearest.json")), "*": FakeResponse(503, {})})
    p = MetOfficePoller(make_client(s), "o", poll_interval=3600, monotonic=mono)
    assert p.poll() is None
    assert "HTTP 503" in caplog.text
    mono.t += MetOfficePoller.RETRY_AFTER_FAILURE
    s.routes["*"] = FakeResponse(200, load_fixture("observations.json"))
    assert p.poll()["temperature"] == 9.13


def test_poller_logs_quota_without_raising(caplog):
    s = FakeSession({"nearest": FakeResponse(429, {})})
    p = MetOfficePoller(make_client(s), "o", poll_interval=3600, monotonic=Mono())
    assert p.poll() is None
    assert "429" in caplog.text
