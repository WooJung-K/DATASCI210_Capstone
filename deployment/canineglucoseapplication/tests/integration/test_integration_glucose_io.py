import pytest, datetime, warnings
from redis import Redis
from redis.exceptions import ResponseError
from testcontainers.redis import RedisContainer

from src.glucose_io import key, write_glucose, get_glucose_history_for_inference
from src.data_models.glucose_reading import GlucoseReading


### Ignore deprecation warning from someone else's package
warnings.filterwarnings(
    "ignore",
    message="The @wait_container_is_ready decorator is deprecated.*",
    category=DeprecationWarning,
)


### Fixtures
@pytest.fixture(scope='function')
def redis_client():
    with RedisContainer("redis:8.6") as redis:
        client = Redis(
            host=redis.get_container_host_ip(),
            port=redis.get_exposed_port(6379),
            decode_responses=True
        )
        yield client

@pytest.fixture
def base_time():
    return datetime.datetime(2025, 3, 22, 17, 44)

@pytest.fixture
def sample_reading():
    return GlucoseReading(
        Device="FreeStyle LibreLink",
        SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
        DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
        RecordType=0,
        Glucose=469
    )

def make_reading(device, serial, ts, glucose):
    return GlucoseReading(
        Device=device,
        SerialNumber=serial,
        DeviceTimestamp=ts,
        RecordType=0,
        Glucose=glucose,
    )

### Tests
# write_glucose()
def test_write_glucose_returned_timestamp_matches_glucosereading_timestamp(redis_client, sample_reading):
    expected_timestamp = int(sample_reading.DeviceTimestamp.timestamp() * 1000)
    r = write_glucose(redis_client, sample_reading)

    assert expected_timestamp == r


def test_write_glucose_stores_expected_timestamp_and_value(redis_client, sample_reading):
    expected_timestamp = int(sample_reading.DeviceTimestamp.timestamp() * 1000)
    r = write_glucose(redis_client, sample_reading)

    k = key(sample_reading)
    result = redis_client.execute_command("TS.GET", k)

    assert result is not None
    assert int(result[0]) == expected_timestamp
    assert int(result[1]) == sample_reading.Glucose


def test_write_glucose_creates_series_on_first_write(redis_client, sample_reading):
    k = key(sample_reading)

    # Check that database is empty
    assert redis_client.exists(k) == 0

    # Create a new timeseries
    write_glucose(redis_client, sample_reading)

    # Check that timeseries exists in the database
    assert redis_client.exists(k) == 1


def test_write_glucose_appends_multiple_points_to_same_series(redis_client, sample_reading):
    reading2 = GlucoseReading(
        Device=sample_reading.Device,
        SerialNumber=sample_reading.SerialNumber,
        DeviceTimestamp=sample_reading.DeviceTimestamp + datetime.timedelta(minutes=5),
        RecordType=0,
        Glucose=200
    )

    write_glucose(redis_client, sample_reading)
    write_glucose(redis_client, reading2)

    results = redis_client.execute_command("TS.RANGE", key(sample_reading), "-", "+")

    assert len(results) == 2
    assert int(results[0][1]) == sample_reading.Glucose
    assert int(results[1][1]) == reading2.Glucose


def test_write_glucose_separates_different_devices_or_serial_numbers(redis_client, sample_reading):
    reading2 = GlucoseReading(
        Device=sample_reading.Device,
        SerialNumber="DIFFERENT-SERIAL",
        DeviceTimestamp=sample_reading.DeviceTimestamp,
        RecordType=0,
        Glucose=123
    )

    write_glucose(redis_client, sample_reading)
    write_glucose(redis_client, reading2)

    result1 = redis_client.execute_command("TS.GET", key(sample_reading))
    result2 = redis_client.execute_command("TS.GET", key(reading2))

    assert key(sample_reading) != key(reading2)
    assert int(result1[1]) == sample_reading.Glucose
    assert int(result2[1]) == reading2.Glucose


def test_write_glucose_raises_on_duplicate_timestamp(redis_client, sample_reading):
    write_glucose(redis_client, sample_reading)

    with pytest.raises(ResponseError):
        write_glucose(redis_client, sample_reading)


# get_glucose_history()
def test_get_glucose_history_returns_points_in_lookback_window(redis_client, sample_reading, base_time):
    serial = sample_reading.SerialNumber
    device = sample_reading.Device

    readings = [
        make_reading(device, serial, base_time - datetime.timedelta(minutes=20), 100),  # outside of window
        make_reading(device, serial, base_time - datetime.timedelta(minutes=15), 110),  # inside the window
        make_reading(device, serial, base_time - datetime.timedelta(minutes=10), 120),
        make_reading(device, serial, base_time - datetime.timedelta(minutes=5), 130),
        make_reading(device, serial, base_time, 140),                                    # inside window
    ]

    for r in readings:
        write_glucose(redis_client, r)

    result = get_glucose_history_for_inference(redis_client, sample_reading)

    assert len(result) == 4
    assert [int(point[1]) for point in result] == [110, 120, 130, 140]

def test_get_glucose_history_returns_empty_list_when_no_points_in_window(redis_client, sample_reading, base_time):
    old_reading = make_reading(
        sample_reading.Device,
        sample_reading.SerialNumber,
        base_time - datetime.timedelta(minutes=30),
        100,
    )
    write_glucose(redis_client, old_reading)

    result = get_glucose_history_for_inference(redis_client, sample_reading)

    assert result == []

def test_get_glucose_history_only_reads_matching_series(redis_client, sample_reading, base_time):
    reading1 = make_reading(
        sample_reading.Device,
        sample_reading.SerialNumber,
        base_time - datetime.timedelta(minutes=5),
        111,
    )
    reading2 = make_reading(
        sample_reading.Device,
        "DIFFERENT-SERIAL",
        base_time - datetime.timedelta(minutes=5),
        222,
    )

    write_glucose(redis_client, reading1)
    write_glucose(redis_client, reading2)

    result = get_glucose_history_for_inference(redis_client, sample_reading)

    assert len(result) == 1
    assert int(result[0][1]) == 111

def test_get_glucose_history_returns_points_in_ascending_timestamp_order(redis_client, sample_reading, base_time):
    readings = [
        make_reading(sample_reading.Device, sample_reading.SerialNumber, base_time - datetime.timedelta(minutes=1), 130),
        make_reading(sample_reading.Device, sample_reading.SerialNumber, base_time - datetime.timedelta(minutes=3), 110),
        make_reading(sample_reading.Device, sample_reading.SerialNumber, base_time - datetime.timedelta(minutes=2), 120),
    ]

    for r in readings:
        write_glucose(redis_client, r)

    result = get_glucose_history_for_inference(redis_client, sample_reading)

    timestamps = [int(point[0]) for point in result]
    values = [int(point[1]) for point in result]

    assert timestamps == sorted(timestamps)
    assert values == [110, 120, 130]

def test_get_glucose_history_includes_start_and_stop_boundaries(redis_client, sample_reading, base_time):
    start_boundary = make_reading(
        sample_reading.Device,
        sample_reading.SerialNumber,
        base_time - datetime.timedelta(minutes=15),
        101,
    )
    stop_boundary = make_reading(
        sample_reading.Device,
        sample_reading.SerialNumber,
        base_time,
        202,
    )

    write_glucose(redis_client, start_boundary)
    write_glucose(redis_client, stop_boundary)

    result = get_glucose_history_for_inference(redis_client, sample_reading)

    assert [int(point[1]) for point in result] == [101, 202]
    