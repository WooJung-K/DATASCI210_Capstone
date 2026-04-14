import datetime
from pydantic import BaseModel, Field, ConfigDict, StrictInt

class GlucoseReading(BaseModel):
    Device: str = Field(min_length=1)
    SerialNumber: str = Field(min_length=1)
    DeviceTimestamp: datetime.datetime
    RecordType: StrictInt = Field(..., ge=0)
    Glucose: int = Field(..., ge=0, le=500)

    # Ignore 'extra' values. Usually we disallow, but this is fast and lazy for a prototype
    model_config = ConfigDict(extra='ignore', str_min_length = 1)

