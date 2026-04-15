import pytest, datetime
from unittest.mock import MagicMock, ANY, call

from src.glucose_io import key, series_key, write_glucose, get_glucose_history_for_inference, get_glucose_range, get_latest_glucose, list_glucose_series
from src.data_models.glucose_reading import GlucoseReading


@pytest.fixture
def sample_reading():
    return GlucoseReading(
        Device="FreeStyle LibreLink",
        SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
        DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
        RecordType=0,
        Glucose=469
    )

# key()
def test_key(sample_reading):
    assert key(sample_reading) == f"{sample_reading.Device}.{sample_reading.SerialNumber}"

# series_key()
def test_series_key_returns_device_dot_serial():
    result = series_key("Dexcom", "ABC123")
    assert result == "Dexcom.ABC123"

# write_glucose()
def test_write_glucose_calls_redis(sample_reading):
    mock_client = MagicMock()
    write_glucose(mock_client, sample_reading)

    mock_client.execute_command.assert_called_with(
        "TS.ADD",
        key(sample_reading),
        ANY,
        sample_reading.Glucose
    )
    
def test_write_glucose_converts_timestamp_to_miliseconds(sample_reading):
    mock_client = MagicMock()
    expected_timestamp = int(sample_reading.DeviceTimestamp.timestamp() * 1000)
    r = write_glucose(mock_client, sample_reading)

    mock_client.execute_command.assert_called_with(
        "TS.ADD",
        key(sample_reading),
        expected_timestamp,
        sample_reading.Glucose
    )

def test_write_glucose_returns_timestamp(sample_reading):
    # Why this is a test: RedisTimeSeries returns the timestamp of each glucose reading when its added to the database
    # This checks that write_glucose returns whatever the database sends back, not whether that value is correct.
    # See integration test_integration_glucose_prediction.py for that test 
    mock_client = MagicMock()
    mock_client.execute_command.return_value = 1234567890

    result = write_glucose(mock_client, sample_reading)

    assert result == 1234567890


# get_glucose_history_for_inference()
def test_get_glucose_history_for_inference_calls_redis(sample_reading):
    mock_client = MagicMock()

    get_glucose_history_for_inference(mock_client, sample_reading)

    mock_client.execute_command.assert_called_once()


def test_get_glucose_history_for_inference_calls_ts_range_with_expected_key(sample_reading):
    mock_client = MagicMock()

    get_glucose_history_for_inference(mock_client, sample_reading)

    call_args = mock_client.execute_command.call_args[0]

    assert call_args[0] == "TS.RANGE"
    assert call_args[1] == key(sample_reading)


def test_get_glucose_history_for_inference_uses_15_minute_lookback(sample_reading):
    mock_client = MagicMock()

    stop_dt = sample_reading.DeviceTimestamp
    start_dt = stop_dt - datetime.timedelta(minutes=15)

    expected_start_time = int(start_dt.timestamp() * 1000)
    expected_stop_time = int(stop_dt.timestamp() * 1000)

    get_glucose_history_for_inference(mock_client, sample_reading)

    mock_client.execute_command.assert_called_with(
        "TS.RANGE",
        key(sample_reading),
        expected_start_time,
        expected_stop_time
    )


def test_get_glucose_history_for_inference_returns_redis_result(sample_reading):
    mock_client = MagicMock()
    expected_result = [
        [1742678940000, "120"],
        [1742679000000, "124"],
        [1742679060000, "127"],
    ]
    mock_client.execute_command.return_value = expected_result

    result = get_glucose_history_for_inference(mock_client, sample_reading)

    assert result == expected_result


def test_get_glucose_history_for_inference_returns_empty_list_when_redis_has_no_data(sample_reading):
    mock_client = MagicMock()
    mock_client.execute_command.return_value = []

    result = get_glucose_history_for_inference(mock_client, sample_reading)

    assert result == []


# get_glucose_range()
def test_get_glucose_range_calls_ts_range_with_millisecond_timestamps():
    redis_client = MagicMock()
    redis_client.execute_command.return_value = [
        (1710000000000, "105"),
        (1710000300000, "110"),
    ]

    start_dt = datetime.datetime(2024, 3, 9, 12, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 3, 9, 13, 0, 0, tzinfo=datetime.timezone.utc)

    result = get_glucose_range(
        redis_client=redis_client,
        device="Dexcom",
        serial_number="ABC123",
        start_dt=start_dt,
        end_dt=end_dt,
    )

    expected_start = int(start_dt.timestamp() * 1000)
    expected_end = int(end_dt.timestamp() * 1000)

    redis_client.execute_command.assert_called_once_with(
        "TS.RANGE",
        "Dexcom.ABC123",
        expected_start,
        expected_end,
    )
    assert result == [
        (1710000000000, "105"),
        (1710000300000, "110"),
    ]


# get_latest_glucose()
def test_get_latest_glucose_calls_ts_get_with_series_key():
    redis_client = MagicMock()
    redis_client.execute_command.return_value = (1710000000000, "117")

    result = get_latest_glucose(
        redis_client=redis_client,
        device="Dexcom",
        serial_number="ABC123",
    )

    redis_client.execute_command.assert_called_once_with(
        "TS.GET",
        "Dexcom.ABC123",
    )
    assert result == (1710000000000, "117")


# list_glucose_series()
def test_list_glucose_series_returns_all_keys_from_single_scan_batch():
    redis_client = MagicMock()
    redis_client.scan.return_value = (
        0,
        ["Dexcom.ABC123", "Libre.XYZ789"],
    )

    result = list_glucose_series(redis_client)

    redis_client.scan.assert_called_once_with(cursor=0, match="*", count=100)
    assert result == ["Dexcom.ABC123", "Libre.XYZ789"]


def test_list_glucose_series_accumulates_keys_across_multiple_scan_calls():
    redis_client = MagicMock()
    redis_client.scan.side_effect = [
        (5, ["Dexcom.ABC123", "Libre.XYZ789"]),
        (9, ["Medtronic.QWE456"]),
        (0, ["Dexcom.DEF111"]),
    ]

    result = list_glucose_series(redis_client)

    assert redis_client.scan.call_count == 3
    redis_client.scan.assert_has_calls(
        [
            call(cursor=0, match="*", count=100),
            call(cursor=5, match="*", count=100),
            call(cursor=9, match="*", count=100),
        ]
    )
    assert result == [
        "Dexcom.ABC123",
        "Libre.XYZ789",
        "Medtronic.QWE456",
        "Dexcom.DEF111",
    ]


def test_list_glucose_series_returns_empty_list_when_no_keys_exist():
    redis_client = MagicMock()
    redis_client.scan.return_value = (0, [])

    result = list_glucose_series(redis_client)

    redis_client.scan.assert_called_once_with(cursor=0, match="*", count=100)
    assert result == []