from pymongo.errors import ServerSelectionTimeoutError

from src.config import MongoConfig
from src.mongo import MongoStore
from tests.conftest import FakeMongoClient

CFG = MongoConfig(True, "mongodb://u:p@h/db", "readings", "house")


def store():
    return MongoStore(CFG, client_factory=FakeMongoClient)


def test_insert_document_shape():
    s = store()
    assert s.insert({"source": "lounge", "temperature": 21.0, "pressure": 1010.0, "humidity": 40.0, "wind": None}, "pi")
    doc = s.collection.docs[0]
    assert list(doc) == ["source", "timestamp", "temperature", "pressure", "humidity", "wind", "deviceName"]
    assert doc["deviceName"] == "pi"
    assert doc["timestamp"].tzinfo is not None


def test_single_client_reused_and_closed():
    s = store()
    s.insert({"source": "a"}, "pi")
    s.insert({"source": "b"}, "pi")
    client = s._client
    assert len(client["readings"]["house"].docs) == 2
    assert client.kwargs["serverSelectionTimeoutMS"] == 10_000
    s.close()
    assert client.closed and s._client is None


def test_observation_dedupe():
    s = store()
    s.insert({"source": "outside", "temperature": 9.0, "observedAt": "2026-11-16T10:00:00Z"}, "pi")
    assert s.observation_exists("outside", "2026-11-16T10:00:00Z")
    assert not s.observation_exists("outside", "2026-11-16T11:00:00Z")


def test_errors_are_logged_without_secrets(caplog):
    s = store()
    s.collection.fail = ServerSelectionTimeoutError("u:p@h timed out")
    assert s.insert({"source": "a"}, "pi") is False
    assert s.observation_exists("outside", "x") is True  # fail safe: don't write duplicates
    assert "ServerSelectionTimeoutError" in caplog.text
    assert "u:p@h" not in caplog.text
