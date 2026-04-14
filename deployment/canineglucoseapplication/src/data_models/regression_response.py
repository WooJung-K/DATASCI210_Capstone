from pydantic import BaseModel, Field, StrictInt

class RegressionResponse(BaseModel):
    Glucose: StrictInt = Field(..., ge=0)