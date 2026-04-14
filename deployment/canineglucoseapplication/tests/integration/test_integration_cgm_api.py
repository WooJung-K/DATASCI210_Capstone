import datetime, pytest
from fastapi.testclient import TestClient
from testcontainers.redis import RedisContainer
from redis import Redis
from unittest.mock import patch

from src import glucose_api
from src.data_models.glucose_reading import GlucoseReading
from src.data_models.upload_response import UploadResponse
from src.glucose_io import key



### Fixtures
@pytest.fixture(autouse=True)
def mock_runtime_services(monkeypatch):
    # Patching in the API call to Twilio
    monkeypatch.setattr("src.runtime_services.owner_phone", "+123")
    monkeypatch.setattr("src.runtime_services.caller_phone", "+456")
    monkeypatch.setattr("src.runtime_services.twilio_client", object())

@pytest.fixture(scope="module")
def redis_container():
    # Uses version 8.6 of redis, because that is what our docker image uses
    with RedisContainer("redis:8.6") as container:
        yield container

@pytest.fixture(scope='module')
def redis_client(redis_container):
    client = Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
        db=0,
        decode_responses=True
    )
    yield client

@pytest.fixture(scope='module')
def client(redis_container): 
    # Point the app's lifespan config at the testcontainer BEFORE startup
    glucose_api.REDIS_HOST_URL = redis_container.get_container_host_ip()
    glucose_api.REDIS_HOST_PORT = int(redis_container.get_exposed_port(6379))

    with TestClient(glucose_api.app) as c:
        yield c

@pytest.fixture
def sample_reading():
    return GlucoseReading(
        Device="FreeStyle LibreLink",
        SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
        DeviceTimestamp=datetime.datetime.now(),
        RecordType=0,
        Glucose=469
    )

### upload endpoint
def test_upload_glucose_reading_returns_status201(client, sample_reading):
    response = client.post(
        "/upload",
        json=sample_reading.model_dump(mode='json')
    )

    assert response.status_code == 201

def test_upload_glucose_reading_returns_payload_of_type_upload_response(client, sample_reading):
    response = client.post(
        "/upload",
        json=sample_reading.model_dump(mode='json')
    )

    expected_key = key(sample_reading)
    expected_timestamp = int(sample_reading.DeviceTimestamp.timestamp()*1000)

    # Validate schema and get data
    data = UploadResponse.model_validate(response.json())

    # Now assert values
    assert data.stored is True
    assert data.device_key == expected_key
    assert data.timestamp_ms == expected_timestamp
    assert data.prediction_status == "queued"


def test_upload_glucose_reading_returns_409_error_on_duplicate_timestamp(client, sample_reading):
    response = client.post(
        "/upload",
        json=sample_reading.model_dump(mode='json')
    )

    assert response.status_code == 201

    response = client.post(
        "/upload",
        json=sample_reading.model_dump(mode='json')
    )

    assert response.status_code == 409
    assert response.json()['detail'] == 'Duplicate timestamp exists for this device'


def test_upload_glucose_write_failure_returns_500(client, sample_reading):
    # patching this in the 'integration testing' module feels like it isn't a best practice
    # but at the same time we're testing the endpoint, not the app <--> db interaction.
    
    with patch(
        "src.cgm_api.write_glucose",
        side_effect=Exception("some other redis problem")
    ):
        response = client.post("/upload", json=sample_reading.model_dump(mode="json"))

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to write glucose reading"


# test that background_task is scheduled on success
# 
# test that background_task is NOT scheduled on failure
# 
# 
