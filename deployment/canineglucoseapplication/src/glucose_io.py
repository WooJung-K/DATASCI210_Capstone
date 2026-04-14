import datetime
from redis import Redis
from redis.exceptions import ResponseError
from src.data_models.glucose_reading import GlucoseReading

def key(reading: GlucoseReading):
    ''' Create database as Device.SerialNumber
    Uses a GlucoseReading from the /upload endpoint.
    '''
    d = reading.Device
    s = reading.SerialNumber
    return f"{d}.{s}"

def series_key(device: str, serial_number: str):
    ''' Create database key as Device.SerialNumber
    Uses device and serial number instead of a GlucoseReading.
    '''
    return f"{device}.{serial_number}"

def write_glucose(redis_client: Redis, reading: GlucoseReading) -> int:
    ''' Write glucose measurement to redis client and return the timestamp logged
    '''
    k = key(reading)
    timestamp = int(reading.DeviceTimestamp.timestamp() * 1000) # RedisTimeSeries uses miliseconds as units of time

    # Use existing connection
    # Create timeseries if it doesn't exist (Device.SerialNumber = timeseries name) 
    # Add timestampped glucose measurement to the appropriate timeseries
    r = redis_client.execute_command(
        "TS.ADD",
        k,
        timestamp,
        reading.Glucose
        )
    return r   

def get_glucose_history_for_inference(redis_client: Redis, reading: GlucoseReading, lookback_minutes: int = 15) -> list: 
    ''' Fetch recent glucose readings from redis (in ms)
    '''
    k = key(reading)

    # Calulate start and stop times
    stop_dt = reading.DeviceTimestamp
    start_dt = stop_dt - datetime.timedelta(minutes=lookback_minutes)

    # Convert to ms so redis can use it
    start_time = int(start_dt.timestamp() * 1000)
    stop_time = int(stop_dt.timestamp() * 1000)

    r = redis_client.execute_command(
        "TS.RANGE", 
        k,
        start_time, 
        stop_time
    )    

    return r

# Helper Functions for D3 Observable
def get_glucose_range(redis_client: Redis, device: str, serial_number: str, start_dt: datetime.datetime, end_dt: datetime.datetime) -> list:
    """Fetch glucose readings for a device/serial over a time range."""
    k = series_key(device, serial_number)

    start_time = int(start_dt.timestamp() * 1000)
    end_time = int(end_dt.timestamp() * 1000)

    result = redis_client.execute_command(
        "TS.RANGE",
        k,
        start_time,
        end_time,
    )
    return result


def get_latest_glucose(redis_client: Redis, device: str, serial_number: str):
    k = series_key(device, serial_number)
    try:
        return redis_client.execute_command("TS.GET", k)
    except ResponseError as e:
        if "key does not exist" in str(e).lower():
            return None
        raise


def list_glucose_series(redis_client: Redis) -> list[str]:
    keys = []
    cursor = 0
    while True:
        cursor, batch = redis_client.scan(cursor=cursor, match="*", count=100)
        keys.extend(batch)
        if cursor == 0:
            break
    return keys