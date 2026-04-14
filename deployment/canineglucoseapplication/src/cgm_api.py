import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

import src.runtime_services as runtime_services

from src.data_models.glucose_reading import GlucoseReading
from src.data_models.upload_response import UploadResponse
from src.glucose_io import key, write_glucose
from src.glucose_inference import run_inference_pipeline


router = APIRouter(tags=["continuous-glucose-monitor"])


def get_redis_client():
    redis_client = runtime_services.redis_client
    if redis_client is None:
        raise HTTPException(status_code=500, detail="database is not initialized")
    return redis_client


def get_twilio_client():
    twilio_client = runtime_services.twilio_client
    if twilio_client is None:
        raise HTTPException(status_code=500, detail="alert service is not initialized")
    return twilio_client


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_glucose_reading(reading: GlucoseReading, background_tasks: BackgroundTasks):
    redis_client = get_redis_client()
    twilio_client = get_twilio_client()

    try:
        inserted_timestamp = write_glucose(redis_client, reading)
    except Exception as e:
        logging.exception("Failed to write glucose reading")

        if "DUPLICATE_POLICY is set to BLOCK mode" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate timestamp exists for this device",
            )

        raise HTTPException(status_code=500, detail="Failed to write glucose reading")

    background_tasks.add_task(
        run_inference_pipeline,
        redis_client,
        twilio_client,
        runtime_services.owner_phone,
        runtime_services.caller_phone,
        reading,
    )

    return UploadResponse(
        stored=True,
        device_key=key(reading),
        timestamp_ms=inserted_timestamp,
        prediction_status="queued",
    )