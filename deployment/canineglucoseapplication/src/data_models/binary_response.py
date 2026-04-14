from pydantic import BaseModel, Field

class BinaryResponse(BaseModel):
    Label: str = Field(min_length=1)