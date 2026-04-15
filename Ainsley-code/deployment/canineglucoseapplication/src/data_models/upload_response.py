from pydantic import BaseModel, Field, StrictBool

class UploadResponse(BaseModel):
    stored: StrictBool
    device_key: str = Field(min_length=1)
    timestamp_ms: int = Field(ge=0)
    prediction_status: str