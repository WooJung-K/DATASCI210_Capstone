import datetime
from pydantic import BaseModel, Field, StrictInt


class GlucosePoint(BaseModel):
    timestamp: datetime.datetime
    glucose: StrictInt = Field(..., ge=0, le=500)
    label: str | None = None
    predicted_label_10m: str | None = None


class GlucoseSeriesResponse(BaseModel):
    device: str
    serial_number: str
    start: datetime.datetime
    end: datetime.datetime
    points: list[GlucosePoint]


class LatestGlucoseResponse(BaseModel):
    device: str
    serial_number: str
    point: GlucosePoint | None


class DeviceSeriesInfo(BaseModel):
    device: str
    serial_number: str


class DeviceSeriesListResponse(BaseModel):
    devices: list[DeviceSeriesInfo]