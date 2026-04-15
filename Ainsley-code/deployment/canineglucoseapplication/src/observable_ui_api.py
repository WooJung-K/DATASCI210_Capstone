import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.exceptions import RedisError

import src.runtime_services as runtime_services

from src.glucose_io import get_glucose_range, get_latest_glucose, list_glucose_series
from src.observable_glucose_formatting import format_range_points, format_latest_point
from src.data_models.observable_glucose_query_models import DeviceSeriesInfo, DeviceSeriesListResponse, GlucoseSeriesResponse, LatestGlucoseResponse

# Create a route within FastAPI
router = APIRouter(prefix="/devices", tags=["observable-ui"])


def get_redis_client():
    redis_client = runtime_services.redis_client
    if redis_client is None:
        raise HTTPException(status_code=500, detail="Redis client is not initialized")
    return redis_client


@router.get("", response_model=DeviceSeriesListResponse)
def get_devices(redis_client=Depends(get_redis_client)):
    try:
        keys = list_glucose_series(redis_client)
    except RedisError:
        raise HTTPException(status_code=500, detail="Failed to list device series")

    devices = []
    for k in keys:
        key_str = k.decode() if isinstance(k, bytes) else str(k)

        parts = key_str.split(".", 1)
        if len(parts) != 2:
            continue

        device, serial_number = parts
        devices.append(
            DeviceSeriesInfo(
                device=device,
                serial_number=serial_number
            )
        )

    return DeviceSeriesListResponse(devices=devices)


@router.get(
    "/{device}/{serial_number}/glucose/latest",
    response_model=LatestGlucoseResponse,
)
def get_latest_device_glucose(
    device: str,
    serial_number: str,
    redis_client=Depends(get_redis_client),
):
    try:
        latest = get_latest_glucose(redis_client, device, serial_number)
    except RedisError:
        raise HTTPException(status_code=500, detail="Failed to fetch latest glucose")

    return LatestGlucoseResponse(
        device=device,
        serial_number=serial_number,
        point=format_latest_point(latest),
    )


@router.get(
    "/{device}/{serial_number}/glucose",
    response_model=GlucoseSeriesResponse,
)
def get_device_glucose_series(
    device: str,
    serial_number: str,
    start: datetime.datetime | None = Query(default=None),
    end: datetime.datetime | None = Query(default=None),
    lookback_minutes: int | None = Query(default=None, ge=1, le=1440),
    limit: int | None = Query(default=None, ge=1, le=10000),
    redis_client=Depends(get_redis_client),
):
    now = datetime.datetime.now(datetime.timezone.utc)

    if end is None:
        end = now

    if start is None:
        if lookback_minutes is None:
            lookback_minutes = 60
        start = end - datetime.timedelta(minutes=lookback_minutes)

    if start >= end:
        raise HTTPException(status_code=400, detail="start must be earlier than end")

    try:
        points = get_glucose_range(
            redis_client=redis_client,
            device=device,
            serial_number=serial_number,
            start_dt=start,
            end_dt=end,
        )
    except RedisError:
        raise HTTPException(status_code=500, detail="Failed to fetch glucose series")

    formatted_points = format_range_points(points)

    if limit is not None:
        formatted_points = formatted_points[-limit:]

    return GlucoseSeriesResponse(
        device=device,
        serial_number=serial_number,
        start=start,
        end=end,
        points=formatted_points,
    )