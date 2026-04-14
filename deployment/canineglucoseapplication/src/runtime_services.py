from fastapi import HTTPException

redis_client = None
twilio_client = None
owner_phone = None
caller_phone = None
enable_alert_calls = False

model_bundle = None


def get_redis_client():
    if redis_client is None:
        raise HTTPException(status_code=500, detail="database is not initialized")
    return redis_client


def get_twilio_client():
    if twilio_client is None:
        raise HTTPException(status_code=500, detail="alert service is not initialized")
    return twilio_client


def get_owner_phone():
    return owner_phone


def get_caller_phone():
    return caller_phone

def get_model_bundle():
    bundle = model_bundle
    if bundle is None:
        raise HTTPException(status_code=500, detail="model bundle is not initialized")
    return bundle