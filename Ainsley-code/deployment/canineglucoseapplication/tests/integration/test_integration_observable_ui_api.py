import datetime
import pytest

from fastapi.testclient import TestClient
from redis import Redis
from testcontainers.redis import RedisContainer

from src import glucose_api
from src.data_models.glucose_reading import GlucoseReading
from src.glucose_io import write_glucose, series_key


@pytest.fixture(autouse=True)
def mock_runtime_services(monkeypatch):
    # Keep startup happy without making real Twilio calls
    monkeypatch.setattr("src.runtime_services.owner_phone", "+123")
    monkeypatch.setattr("src.runtime_services.caller_phone", "+456")
    monkeypatch.setattr("src.runtime_services.twilio_client", object())


@pytest.fixture(scope="module")
def redis_container():
    # Use the same image/pattern you are already using elsewhere.
    # This assumes the container actually supports TS.* commands.
    with RedisContainer("redis:8.6") as container:
        yield container


@pytest.fixture(scope="module")
def redis_client(redis_container):
    client = Redis(
        host=redis_container.get_container_host_ip(),
        port=int(redis_container.get_exposed_port(6379)),
        db=0,
        decode_responses=True,
    )
    yield client
    client.close()


@pytest.fixture(scope="module")
def client(redis_container):
    glucose_api.REDIS_HOST_URL = redis_container.get_container_host_ip()
    glucose_api.REDIS_HOST_PORT = int(redis_container.get_exposed_port(6379))

    # Keep lifespan startup happy
    glucose_api.TWILIO_API_KEY = "test-key"
    glucose_api.TWILIO_API_SECRET = "test-secret"
    glucose_api.OWNER_PHONE = "+123"
    glucose_api.CALLER_PHONE = "+456"

    with TestClient(glucose_api.app) as c:
        yield c


@pytest.fixture
def base_time():
    return datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.timezone.utc)


def make_reading(device, serial, ts, glucose):
    return GlucoseReading(
        Device=device,
        SerialNumber=serial,
        DeviceTimestamp=ts,
        RecordType=0,
        Glucose=glucose,
    )


def test_get_devices_returns_known_series(client, redis_client, base_time):
    reading1 = make_reading(
        "FreeStyle LibreLink",
        "SERIAL-ONE",
        base_time,
        140,
    )
    reading2 = make_reading(
        "Dexcom",
        "SERIAL-TWO",
        base_time,
        180,
    )

    write_glucose(redis_client, reading1)
    write_glucose(redis_client, reading2)

    response = client.get("/devices")

    assert response.status_code == 200

    payload = response.json()
    assert "devices" in payload

    returned_pairs = {
        (item["device"], item["serial_number"])
        for item in payload["devices"]
    }

    assert ("FreeStyle LibreLink", "SERIAL-ONE") in returned_pairs
    assert ("Dexcom", "SERIAL-TWO") in returned_pairs


def test_get_latest_device_glucose_returns_latest_point(client, redis_client, base_time):
    device = "FreeStyle LibreLink"
    serial = "LATEST-SERIAL"

    older = make_reading(device, serial, base_time - datetime.timedelta(minutes=5), 110)
    latest = make_reading(device, serial, base_time, 260)

    write_glucose(redis_client, older)
    write_glucose(redis_client, latest)

    response = client.get(f"/devices/{device}/{serial}/glucose/latest")

    assert response.status_code == 200

    payload = response.json()
    assert payload["device"] == device
    assert payload["serial_number"] == serial
    assert payload["point"] is not None

    point = payload["point"]
    assert point["glucose"] == 260
    assert point["label"] == "hyperglycemia"
    assert point["predicted_label_10m"] is None

    parsed_ts = datetime.datetime.fromisoformat(point["timestamp"].replace("Z", "+00:00"))
    assert parsed_ts == base_time


def test_get_latest_device_glucose_returns_none_when_series_missing(client):
    response = client.get("/devices/NoSuchDevice/NoSuchSerial/glucose/latest")

    assert response.status_code == 200

    payload = response.json()
    assert payload["device"] == "NoSuchDevice"
    assert payload["serial_number"] == "NoSuchSerial"
    assert payload["point"] is None


def test_get_device_glucose_series_returns_points_in_window(client, redis_client, base_time):
    device = "FreeStyle LibreLink"
    serial = "RANGE-SERIAL"

    readings = [
        make_reading(device, serial, base_time - datetime.timedelta(minutes=20), 100),  # outside
        make_reading(device, serial, base_time - datetime.timedelta(minutes=15), 64),
        make_reading(device, serial, base_time - datetime.timedelta(minutes=10), 100),
        make_reading(device, serial, base_time - datetime.timedelta(minutes=5), 251),
        make_reading(device, serial, base_time, 140),
    ]

    for reading in readings:
        write_glucose(redis_client, reading)

    start = (base_time - datetime.timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
    end = base_time.isoformat().replace("+00:00", "Z")

    response = client.get(
        f"/devices/{device}/{serial}/glucose",
        params={"start": start, "end": end},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["device"] == device
    assert payload["serial_number"] == serial
    assert len(payload["points"]) == 4

    glucose_values = [point["glucose"] for point in payload["points"]]
    labels = [point["label"] for point in payload["points"]]

    assert glucose_values == [64, 100, 251, 140]
    assert labels == ["hypoglycemia", "normal", "hyperglycemia", "normal"]

    returned_times = [
        datetime.datetime.fromisoformat(point["timestamp"].replace("Z", "+00:00"))
        for point in payload["points"]
    ]
    assert returned_times == sorted(returned_times)


def test_get_device_glucose_series_applies_limit_to_last_n_points(client, redis_client, base_time):
    device = "FreeStyle LibreLink"
    serial = "LIMIT-SERIAL"

    readings = [
        make_reading(device, serial, base_time - datetime.timedelta(minutes=15), 100),
        make_reading(device, serial, base_time - datetime.timedelta(minutes=10), 110),
        make_reading(device, serial, base_time - datetime.timedelta(minutes=5), 120),
        make_reading(device, serial, base_time, 130),
    ]

    for reading in readings:
        write_glucose(redis_client, reading)

    start = (base_time - datetime.timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
    end = base_time.isoformat().replace("+00:00", "Z")

    response = client.get(
        f"/devices/{device}/{serial}/glucose",
        params={"start": start, "end": end, "limit": 2},
    )

    assert response.status_code == 200

    payload = response.json()
    assert len(payload["points"]) == 2
    assert [point["glucose"] for point in payload["points"]] == [120, 130]


def test_get_device_glucose_series_returns_400_when_start_after_end(client, base_time):
    device = "FreeStyle LibreLink"
    serial = "BAD-WINDOW-SERIAL"

    start = base_time.isoformat().replace("+00:00", "Z")
    end = (base_time - datetime.timedelta(minutes=1)).isoformat().replace("+00:00", "Z")

    response = client.get(
        f"/devices/{device}/{serial}/glucose",
        params={"start": start, "end": end},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "start must be earlier than end"


def test_get_device_glucose_series_returns_422_for_invalid_limit(client, base_time):
    device = "FreeStyle LibreLink"
    serial = "VALIDATION-SERIAL"

    start = (base_time - datetime.timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
    end = base_time.isoformat().replace("+00:00", "Z")

    response = client.get(
        f"/devices/{device}/{serial}/glucose",
        params={"start": start, "end": end, "limit": 0},
    )

    assert response.status_code == 422