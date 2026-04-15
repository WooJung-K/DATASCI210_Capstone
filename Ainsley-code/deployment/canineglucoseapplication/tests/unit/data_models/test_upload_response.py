import pytest
from pydantic import ValidationError

from src.data_models.upload_response import UploadResponse


def test_valid_response_model():
    m = UploadResponse(
        stored=True,
        device_key="device.123",
        timestamp_ms=1742679840000,
        prediction_status="queued",
    )

    assert m.stored is True
    assert m.device_key == "device.123"
    assert m.timestamp_ms == 1742679840000
    assert m.prediction_status == "queued"


@pytest.mark.parametrize("missing_field", [
    "stored",
    "device_key",
    "timestamp_ms",
    "prediction_status",
])
def test_missing_required_fields_raise_error(missing_field):
    payload = {
        "stored": True,
        "device_key": "device.123",
        "timestamp_ms": 1742679840000,
        "prediction_status": "queued",
    }

    del payload[missing_field]

    with pytest.raises(ValidationError):
        UploadResponse(**payload)

@pytest.mark.parametrize("bad_payload", [
    {"stored": "yes", "device_key": "device.123", "timestamp_ms": 1, "prediction_status": "queued"},
    {"stored": True, "device_key": 123, "timestamp_ms": 1, "prediction_status": "queued"},
    {"stored": True, "device_key": "device.123", "timestamp_ms": "one seven four two six", "prediction_status": "queued"},
    {"stored": True, "device_key": "device.123", "timestamp_ms": 1, "prediction_status": 123},
])
def test_invalid_types_raise_validation_error(bad_payload):
    with pytest.raises(ValidationError):
        UploadResponse(**bad_payload)


def test_model_serialization_to_dict():
    m = UploadResponse(
        stored=True,
        device_key="device.123",
        timestamp_ms=1742679840000,
        prediction_status="queued",
    )

    d = m.model_dump()

    assert d == {
        "stored": True,
        "device_key": "device.123",
        "timestamp_ms": 1742679840000,
        "prediction_status": "queued",
    }