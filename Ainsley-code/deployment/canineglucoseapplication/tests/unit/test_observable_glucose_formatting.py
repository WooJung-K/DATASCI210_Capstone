import datetime
import pytest

from src.observable_glucose_formatting import (
    glucose_label,
    ms_to_datetime_utc,
    format_range_points,
    format_latest_point,
)


def to_ms(dt: datetime.datetime) -> int:
    return int(dt.timestamp() * 1000)


@pytest.mark.parametrize(
    "glucose_value, expected_label",
    [
        (0, "hypoglycemia"),
        (64, "hypoglycemia"),
        (65, "normal"),
        (100, "normal"),
        (250, "normal"),
        (251, "hyperglycemia"),
        (500, "hyperglycemia"),
    ],
)
def test_glucose_label_applies_expected_thresholds(glucose_value, expected_label):
    assert glucose_label(glucose_value) == expected_label


def test_ms_to_datetime_utc_converts_epoch_zero():
    result = ms_to_datetime_utc(0)

    assert result == datetime.datetime(1970, 1, 1, 0, 0, tzinfo=datetime.UTC)


def test_ms_to_datetime_utc_converts_known_timestamp():
    expected = datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.UTC)
    timestamp_ms = to_ms(expected)

    result = ms_to_datetime_utc(timestamp_ms)

    assert result == expected


def test_format_range_points_returns_empty_list_for_empty_input():
    result = format_range_points([])

    assert result == []


def test_format_range_points_formats_integer_values():
    ts1 = datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.UTC)
    ts2 = datetime.datetime(2025, 3, 22, 17, 59, tzinfo=datetime.UTC)
    ts3 = datetime.datetime(2025, 3, 22, 18, 14, tzinfo=datetime.UTC)

    redis_points = [
        [to_ms(ts1), 64],
        [to_ms(ts2), 65],
        [to_ms(ts3), 251],
    ]

    result = format_range_points(redis_points)

    assert len(result) == 3

    assert result[0] == {
        "timestamp": ts1,
        "glucose": 64,
        "label": "hypoglycemia",
        "predicted_label_10m": None,
    }

    assert result[1] == {
        "timestamp": ts2,
        "glucose": 65,
        "label": "normal",
        "predicted_label_10m": None,
    }

    assert result[2] == {
        "timestamp": ts3,
        "glucose": 251,
        "label": "hyperglycemia",
        "predicted_label_10m": None,
    }


def test_format_range_points_formats_float_values():
    ts1 = datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.UTC)
    ts2 = datetime.datetime(2025, 3, 22, 17, 59, tzinfo=datetime.UTC)

    redis_points = [
        [to_ms(ts1), 192.0],
        [to_ms(ts2), 251.0],
    ]

    result = format_range_points(redis_points)

    assert result[0]["glucose"] == 192
    assert result[0]["label"] == "normal"

    assert result[1]["glucose"] == 251
    assert result[1]["label"] == "hyperglycemia"


def test_format_range_points_formats_string_numeric_values():
    ts1 = datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.UTC)
    ts2 = datetime.datetime(2025, 3, 22, 17, 59, tzinfo=datetime.UTC)
    ts3 = datetime.datetime(2025, 3, 22, 18, 14, tzinfo=datetime.UTC)

    redis_points = [
        [to_ms(ts1), "64"],
        [to_ms(ts2), "65.0"],
        [to_ms(ts3), "251"],
    ]

    result = format_range_points(redis_points)

    assert result[0]["glucose"] == 64
    assert result[0]["label"] == "hypoglycemia"

    assert result[1]["glucose"] == 65
    assert result[1]["label"] == "normal"

    assert result[2]["glucose"] == 251
    assert result[2]["label"] == "hyperglycemia"


def test_format_range_points_preserves_order():
    ts1 = datetime.datetime(2025, 3, 22, 18, 14, tzinfo=datetime.UTC)
    ts2 = datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.UTC)
    ts3 = datetime.datetime(2025, 3, 22, 17, 59, tzinfo=datetime.UTC)

    redis_points = [
        [to_ms(ts1), 251],
        [to_ms(ts2), 64],
        [to_ms(ts3), 65],
    ]

    result = format_range_points(redis_points)

    assert result[0]["timestamp"] == ts1
    assert result[1]["timestamp"] == ts2
    assert result[2]["timestamp"] == ts3


def test_format_range_points_rejects_non_numeric_glucose():
    ts = datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.UTC)

    redis_points = [
        [to_ms(ts), "not-a-number"],
    ]

    with pytest.raises(ValueError):
        format_range_points(redis_points)


def test_format_latest_point_returns_none_for_none():
    assert format_latest_point(None) is None


def test_format_latest_point_returns_none_for_empty_list():
    assert format_latest_point([]) is None


def test_format_latest_point_formats_integer_value():
    ts = datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.UTC)
    redis_point = [to_ms(ts), 64]

    result = format_latest_point(redis_point)

    assert result == {
        "timestamp": ts,
        "glucose": 64,
        "label": "hypoglycemia",
        "predicted_label_10m": None,
    }


def test_format_latest_point_formats_float_and_string_values():
    ts = datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.UTC)

    float_result = format_latest_point([to_ms(ts), 251.0])
    string_result = format_latest_point([to_ms(ts), "65.0"])

    assert float_result["glucose"] == 251
    assert float_result["label"] == "hyperglycemia"

    assert string_result["glucose"] == 65
    assert string_result["label"] == "normal"


def test_format_latest_point_rejects_non_numeric_glucose():
    ts = datetime.datetime(2025, 3, 22, 17, 44, tzinfo=datetime.UTC)

    with pytest.raises(ValueError):
        format_latest_point([to_ms(ts), "banana"])