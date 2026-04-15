import datetime
import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError

import src.runtime_services as runtime_services
from src.observable_ui_api import (
    get_redis_client,
    get_devices,
    get_latest_device_glucose,
    get_device_glucose_series,
)


def test_get_redis_client_returns_initialized_client():
    sentinel = object()
    old_client = runtime_services.redis_client
    runtime_services.redis_client = sentinel

    try:
        result = get_redis_client()
        assert result is sentinel
    finally:
        runtime_services.redis_client = old_client


def test_get_redis_client_raises_if_not_initialized():
    old_client = runtime_services.redis_client
    runtime_services.redis_client = None

    try:
        with pytest.raises(HTTPException) as exc_info:
            get_redis_client()

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Redis client is not initialized"
    finally:
        runtime_services.redis_client = old_client


def test_get_devices_returns_device_series_list(monkeypatch):
    fake_keys = [
        "FreeStyle LibreLink.E9A0CE98-AA19-4E58-8F27-31A26580354B",
        b"Dexcom.xyz789",
        "invalidkeywithoutdot",
    ]

    def fake_list_glucose_series(redis_client):
        return fake_keys

    monkeypatch.setattr(
        "src.observable_ui_api.list_glucose_series",
        fake_list_glucose_series,
    )

    result = get_devices(redis_client=object())

    assert result.devices[0].device == "FreeStyle LibreLink"
    assert result.devices[0].serial_number == "E9A0CE98-AA19-4E58-8F27-31A26580354B"

    assert result.devices[1].device == "Dexcom"
    assert result.devices[1].serial_number == "xyz789"


def test_get_devices_raises_500_on_redis_error(monkeypatch):
    def fake_list_glucose_series(redis_client):
        raise RedisError("boom")

    monkeypatch.setattr(
        "src.observable_ui_api.list_glucose_series",
        fake_list_glucose_series,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_devices(redis_client=object())

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to list device series"


def test_get_latest_device_glucose_returns_formatted_point(monkeypatch):
    fake_latest = [1742679840000, "192"]

    def fake_get_latest_glucose(redis_client, device, serial_number):
        assert device == "FreeStyle LibreLink"
        assert serial_number == "abc123"
        return fake_latest

    def fake_format_latest_point(redis_point):
        assert redis_point == fake_latest
        return {
            "timestamp": datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.timezone.utc),
            "glucose": 192,
            "label": "normal",
            "predicted_label_10m": None,
        }

    monkeypatch.setattr(
        "src.observable_ui_api.get_latest_glucose",
        fake_get_latest_glucose,
    )
    monkeypatch.setattr(
        "src.observable_ui_api.format_latest_point",
        fake_format_latest_point,
    )

    result = get_latest_device_glucose(
        device="FreeStyle LibreLink",
        serial_number="abc123",
        redis_client=object(),
    )

    assert result.device == "FreeStyle LibreLink"
    assert result.serial_number == "abc123"
    assert result.point is not None
    assert result.point.glucose == 192
    assert result.point.label == "normal"
    assert result.point.predicted_label_10m is None


def test_get_latest_device_glucose_raises_500_on_redis_error(monkeypatch):
    def fake_get_latest_glucose(redis_client, device, serial_number):
        raise RedisError("boom")

    monkeypatch.setattr(
        "src.observable_ui_api.get_latest_glucose",
        fake_get_latest_glucose,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_latest_device_glucose(
            device="FreeStyle LibreLink",
            serial_number="abc123",
            redis_client=object(),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to fetch latest glucose"


def test_get_device_glucose_series_uses_default_lookback_and_returns_points(monkeypatch):
    fixed_now = datetime.datetime(2026, 4, 8, 12, 0, tzinfo=datetime.timezone.utc)
    fake_points = [
        [1742679840000, "64"],
        [1742680740000, "251"],
    ]

    class FixedDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    def fake_get_glucose_range(redis_client, device, serial_number, start_dt, end_dt):
        assert device == "FreeStyle LibreLink"
        assert serial_number == "abc123"
        assert end_dt == fixed_now
        assert start_dt == fixed_now - datetime.timedelta(minutes=60)
        return fake_points

    def fake_format_range_points(points):
        assert points == fake_points
        return [
            {
                "timestamp": datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.timezone.utc),
                "glucose": 64,
                "label": "hypoglycemia",
                "predicted_label_10m": None,
            },
            {
                "timestamp": datetime.datetime(2025, 3, 22, 17, 59, tzinfo=datetime.timezone.utc),
                "glucose": 251,
                "label": "hyperglycemia",
                "predicted_label_10m": None,
            },
        ]

    monkeypatch.setattr("src.observable_ui_api.datetime.datetime", FixedDatetime)
    monkeypatch.setattr(
        "src.observable_ui_api.get_glucose_range",
        fake_get_glucose_range,
    )
    monkeypatch.setattr(
        "src.observable_ui_api.format_range_points",
        fake_format_range_points,
    )

    result = get_device_glucose_series(
        device="FreeStyle LibreLink",
        serial_number="abc123",
        start=None,
        end=None,
        lookback_minutes=None,
        limit=None,
        redis_client=object(),
    )

    assert result.device == "FreeStyle LibreLink"
    assert result.serial_number == "abc123"
    assert result.start == fixed_now - datetime.timedelta(minutes=60)
    assert result.end == fixed_now
    assert len(result.points) == 2
    assert result.points[0].glucose == 64
    assert result.points[1].glucose == 251


def test_get_device_glucose_series_uses_explicit_start_end(monkeypatch):
    start = datetime.datetime(2026, 4, 8, 10, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 4, 8, 11, 0, tzinfo=datetime.timezone.utc)

    def fake_get_glucose_range(redis_client, device, serial_number, start_dt, end_dt):
        assert start_dt == start
        assert end_dt == end
        return []

    monkeypatch.setattr(
        "src.observable_ui_api.get_glucose_range",
        fake_get_glucose_range,
    )
    monkeypatch.setattr(
        "src.observable_ui_api.format_range_points",
        lambda points: [],
    )

    result = get_device_glucose_series(
        device="FreeStyle LibreLink",
        serial_number="abc123",
        start=start,
        end=end,
        lookback_minutes=15,
        limit=None,
        redis_client=object(),
    )

    assert result.start == start
    assert result.end == end
    assert result.points == []


def test_get_device_glucose_series_applies_limit_to_last_n_points(monkeypatch):
    formatted = [
        {
            "timestamp": datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.timezone.utc),
            "glucose": 100,
            "label": "normal",
            "predicted_label_10m": None,
        },
        {
            "timestamp": datetime.datetime(2025, 3, 22, 17, 59, tzinfo=datetime.timezone.utc),
            "glucose": 110,
            "label": "normal",
            "predicted_label_10m": None,
        },
        {
            "timestamp": datetime.datetime(2025, 3, 22, 18, 14, tzinfo=datetime.timezone.utc),
            "glucose": 120,
            "label": "normal",
            "predicted_label_10m": None,
        },
    ]

    monkeypatch.setattr(
        "src.observable_ui_api.get_glucose_range",
        lambda redis_client, device, serial_number, start_dt, end_dt: ["unused"],
    )
    monkeypatch.setattr(
        "src.observable_ui_api.format_range_points",
        lambda points: formatted,
    )

    start = datetime.datetime(2026, 4, 8, 10, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 4, 8, 11, 0, tzinfo=datetime.timezone.utc)

    result = get_device_glucose_series(
        device="FreeStyle LibreLink",
        serial_number="abc123",
        start=start,
        end=end,
        lookback_minutes=None,
        limit=2,
        redis_client=object(),
    )

    assert len(result.points) == 2
    assert result.points[0].glucose == 110
    assert result.points[1].glucose == 120


def test_get_device_glucose_series_raises_400_if_start_not_before_end():
    start = datetime.datetime(2026, 4, 8, 11, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 4, 8, 10, 0, tzinfo=datetime.timezone.utc)

    with pytest.raises(HTTPException) as exc_info:
        get_device_glucose_series(
            device="FreeStyle LibreLink",
            serial_number="abc123",
            start=start,
            end=end,
            lookback_minutes=None,
            limit=None,
            redis_client=object(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "start must be earlier than end"


def test_get_device_glucose_series_raises_500_on_redis_error(monkeypatch):
    def fake_get_glucose_range(redis_client, device, serial_number, start_dt, end_dt):
        raise RedisError("boom")

    monkeypatch.setattr(
        "src.observable_ui_api.get_glucose_range",
        fake_get_glucose_range,
    )

    start = datetime.datetime(2026, 4, 8, 10, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 4, 8, 11, 0, tzinfo=datetime.timezone.utc)

    with pytest.raises(HTTPException) as exc_info:
        get_device_glucose_series(
            device="FreeStyle LibreLink",
            serial_number="abc123",
            start=start,
            end=end,
            lookback_minutes=None,
            limit=None,
            redis_client=object(),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to fetch glucose series"