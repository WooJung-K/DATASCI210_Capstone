import datetime
import pytest
from pydantic import ValidationError

from src.data_models.observable_glucose_query_models import (
    GlucosePoint,
    GlucoseSeriesResponse,
    LatestGlucoseResponse,
    DeviceSeriesInfo,
    DeviceSeriesListResponse,
)


def test_glucose_point_accepts_valid_payload():
    ts = datetime.datetime(2026, 4, 4, 15, 20, tzinfo=datetime.timezone.utc)

    point = GlucosePoint(
        timestamp=ts,
        glucose=192,
        label="hyperglycemia",
        predicted_label_10m="hyperglycemia",
    )

    assert point.timestamp == ts
    assert point.glucose == 192
    assert point.label == "hyperglycemia"
    assert point.predicted_label_10m == "hyperglycemia"


def test_glucose_point_defaults_optional_fields_to_none():
    ts = datetime.datetime(2026, 4, 4, 15, 20, tzinfo=datetime.timezone.utc)

    point = GlucosePoint(
        timestamp=ts,
        glucose=192,
    )

    assert point.timestamp == ts
    assert point.glucose == 192
    assert point.label is None
    assert point.predicted_label_10m is None


@pytest.mark.parametrize(
    "ts",
    [
        "2026-04-04 15:20:00",
        "2026-04-04T15:20:00",
        "2026-04-04T15:20:00Z",
        "2026-04-04T15:20:00-04:00",
    ],
)
def test_glucose_point_accepts_parseable_datetime_strings(ts):
    point = GlucosePoint(
        timestamp=ts,
        glucose=192,
    )

    assert isinstance(point.timestamp, datetime.datetime)
    assert point.glucose == 192


@pytest.mark.parametrize("bad_payload", [
    {"timestamp": None, "glucose": 192},
    {"timestamp": ["2026-04-04T15:20:00Z"], "glucose": 192},
    {"timestamp": {"when": "2026-04-04T15:20:00Z"}, "glucose": 192},
])
def test_glucose_point_rejects_invalid_timestamp_types(bad_payload):
    with pytest.raises(ValidationError):
        GlucosePoint(**bad_payload)


@pytest.mark.parametrize("bad_glucose", [
    "192",
    192.0,
    192.5,
    True,
    None,
    [192],
    {"glucose": 192},
])
def test_glucose_point_rejects_invalid_glucose_types(bad_glucose):
    with pytest.raises(ValidationError):
        GlucosePoint(
            timestamp=datetime.datetime(2026, 4, 4, 15, 20),
            glucose=bad_glucose,
        )


def test_glucose_series_response_accepts_valid_payload():
    start = datetime.datetime(2026, 4, 4, 15, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 4, 4, 16, 0, tzinfo=datetime.timezone.utc)

    response = GlucoseSeriesResponse(
        device="FreeStyle LibreLink",
        serial_number="E9A0CE98-AA19-4E58-8F27-31A26580354B",
        start=start,
        end=end,
        points=[
            GlucosePoint(
                timestamp=datetime.datetime(2026, 4, 4, 15, 20, tzinfo=datetime.timezone.utc),
                glucose=192,
                label="hyperglycemia",
                predicted_label_10m="hyperglycemia",
            ),
            GlucosePoint(
                timestamp=datetime.datetime(2026, 4, 4, 15, 35, tzinfo=datetime.timezone.utc),
                glucose=184,
                label="hyperglycemia",
                predicted_label_10m=None,
            ),
        ],
    )

    assert response.device == "FreeStyle LibreLink"
    assert response.serial_number == "E9A0CE98-AA19-4E58-8F27-31A26580354B"
    assert response.start == start
    assert response.end == end
    assert len(response.points) == 2
    assert response.points[0].glucose == 192
    assert response.points[1].predicted_label_10m is None


def test_glucose_series_response_accepts_nested_dicts_for_points():
    response = GlucoseSeriesResponse(
        device="FreeStyle LibreLink",
        serial_number="abc123",
        start="2026-04-04T15:00:00Z",
        end="2026-04-04T16:00:00Z",
        points=[
            {
                "timestamp": "2026-04-04T15:20:00Z",
                "glucose": 192,
                "label": "hyperglycemia",
                "predicted_label_10m": "hyperglycemia",
            }
        ],
    )

    assert response.device == "FreeStyle LibreLink"
    assert response.serial_number == "abc123"
    assert len(response.points) == 1
    assert isinstance(response.points[0], GlucosePoint)
    assert response.points[0].glucose == 192


@pytest.mark.parametrize("missing_field", [
    "device",
    "serial_number",
    "start",
    "end",
    "points",
])
def test_glucose_series_response_missing_required_fields_raise_error(missing_field):
    payload = {
        "device": "FreeStyle LibreLink",
        "serial_number": "abc123",
        "start": "2026-04-04T15:00:00Z",
        "end": "2026-04-04T16:00:00Z",
        "points": [],
    }

    del payload[missing_field]

    with pytest.raises(ValidationError):
        GlucoseSeriesResponse(**payload)


@pytest.mark.parametrize("bad_points", [
    None,
    "not-a-list",
    123,
    {"timestamp": "2026-04-04T15:20:00Z", "glucose": 192},
])
def test_glucose_series_response_rejects_invalid_points_container(bad_points):
    with pytest.raises(ValidationError):
        GlucoseSeriesResponse(
            device="FreeStyle LibreLink",
            serial_number="abc123",
            start="2026-04-04T15:00:00Z",
            end="2026-04-04T16:00:00Z",
            points=bad_points,
        )


def test_glucose_series_response_rejects_invalid_point_item():
    with pytest.raises(ValidationError):
        GlucoseSeriesResponse(
            device="FreeStyle LibreLink",
            serial_number="abc123",
            start="2026-04-04T15:00:00Z",
            end="2026-04-04T16:00:00Z",
            points=[
                {
                    "timestamp": "2026-04-04T15:20:00Z",
                    "glucose": "192",  # invalid
                }
            ],
        )


def test_latest_glucose_response_accepts_point():
    response = LatestGlucoseResponse(
        device="FreeStyle LibreLink",
        serial_number="abc123",
        point={
            "timestamp": "2026-04-04T15:20:00Z",
            "glucose": 192,
            "label": "hyperglycemia",
            "predicted_label_10m": "hyperglycemia",
        },
    )

    assert response.device == "FreeStyle LibreLink"
    assert response.serial_number == "abc123"
    assert isinstance(response.point, GlucosePoint)
    assert response.point.glucose == 192


def test_latest_glucose_response_accepts_none_point():
    response = LatestGlucoseResponse(
        device="FreeStyle LibreLink",
        serial_number="abc123",
        point=None,
    )

    assert response.device == "FreeStyle LibreLink"
    assert response.serial_number == "abc123"
    assert response.point is None


@pytest.mark.parametrize("missing_field", [
    "device",
    "serial_number",
    "point",
])
def test_latest_glucose_response_missing_required_fields_raise_error(missing_field):
    payload = {
        "device": "FreeStyle LibreLink",
        "serial_number": "abc123",
        "point": None,
    }

    del payload[missing_field]

    with pytest.raises(ValidationError):
        LatestGlucoseResponse(**payload)


def test_device_series_info_accepts_valid_payload():
    info = DeviceSeriesInfo(
        device="FreeStyle LibreLink",
        serial_number="abc123",
    )

    assert info.device == "FreeStyle LibreLink"
    assert info.serial_number == "abc123"


@pytest.mark.parametrize("missing_field", [
    "device",
    "serial_number",
])
def test_device_series_info_missing_required_fields_raise_error(missing_field):
    payload = {
        "device": "FreeStyle LibreLink",
        "serial_number": "abc123",
    }

    del payload[missing_field]

    with pytest.raises(ValidationError):
        DeviceSeriesInfo(**payload)


def test_device_series_list_response_accepts_valid_payload():
    response = DeviceSeriesListResponse(
        devices=[
            DeviceSeriesInfo(
                device="FreeStyle LibreLink",
                serial_number="abc123",
            ),
            DeviceSeriesInfo(
                device="Dexcom",
                serial_number="xyz789",
            ),
        ]
    )

    assert len(response.devices) == 2
    assert response.devices[0].device == "FreeStyle LibreLink"
    assert response.devices[1].serial_number == "xyz789"


def test_device_series_list_response_accepts_nested_dicts():
    response = DeviceSeriesListResponse(
        devices=[
            {
                "device": "FreeStyle LibreLink",
                "serial_number": "abc123",
            }
        ]
    )

    assert len(response.devices) == 1
    assert isinstance(response.devices[0], DeviceSeriesInfo)


@pytest.mark.parametrize("bad_devices", [
    None,
    "not-a-list",
    123,
    {"device": "FreeStyle LibreLink", "serial_number": "abc123"},
])
def test_device_series_list_response_rejects_invalid_devices_container(bad_devices):
    with pytest.raises(ValidationError):
        DeviceSeriesListResponse(devices=bad_devices)


def test_device_series_list_response_rejects_invalid_device_item():
    with pytest.raises(ValidationError):
        DeviceSeriesListResponse(
            devices=[
                {
                    "device": "FreeStyle LibreLink",
                    # missing serial_number
                }
            ]
        )


def test_glucose_series_response_model_dump_serializes_nested_models():
    response = GlucoseSeriesResponse(
        device="FreeStyle LibreLink",
        serial_number="abc123",
        start=datetime.datetime(2026, 4, 4, 15, 0, tzinfo=datetime.timezone.utc),
        end=datetime.datetime(2026, 4, 4, 16, 0, tzinfo=datetime.timezone.utc),
        points=[
            GlucosePoint(
                timestamp=datetime.datetime(2026, 4, 4, 15, 20, tzinfo=datetime.timezone.utc),
                glucose=192,
                label="hyperglycemia",
                predicted_label_10m=None,
            )
        ],
    )

    dumped = response.model_dump()

    assert dumped["device"] == "FreeStyle LibreLink"
    assert dumped["serial_number"] == "abc123"
    assert isinstance(dumped["points"], list)
    assert dumped["points"][0]["glucose"] == 192
    assert dumped["points"][0]["label"] == "hyperglycemia"
    assert dumped["points"][0]["predicted_label_10m"] is None