import datetime, logging

from contextlib import asynccontextmanager
from os import getenv
from fastapi import FastAPI
from joblib import load
from redis import Redis
from redis.exceptions import RedisError
from twilio.rest import Client as TwilioClient

import src.runtime_services as runtime_services

from src.observable_ui_api import router as observable_ui_router
from src.cgm_api import router as cgm_router
from model.model_inference import load_inference_bundle





### Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)

# Redis connection info
LOCAL_REDIS_URL = "localhost"
LOCAL_REDIS_PORT = '6379'
REDIS_HOST_URL = getenv('REDIS', default=LOCAL_REDIS_URL)
REDIS_HOST_PORT = getenv('REDIS_PORT', default=LOCAL_REDIS_PORT)


# Twilio connection info
TWILIO_API_KEY = getenv("TWILIO_API_KEY")
TWILIO_API_SECRET = getenv("TWILIO_API_SECRET")
OWNER_PHONE = getenv("OWNER_PHONE")
CALLER_PHONE = getenv("CALLER_PHONE")
ENABLE_ALERT_CALLS = getenv("ENABLE_ALERT_CALLS", "false").lower() == "true"
runtime_services.enable_alert_calls = ENABLE_ALERT_CALLS


# Define API Lifespan (Redis Connection, Load Model, Etc)
@asynccontextmanager
async def lifespan_mechanism(app: FastAPI):
    logging.info("Starting up CanineGlucose API")

    # Load the glucose inference model
    runtime_services.model_bundle = load_inference_bundle('model/cgi_model_bundle.pkl')

    # Connect to Redis
    runtime_services.redis_client = Redis(
        host=REDIS_HOST_URL,
        port=REDIS_HOST_PORT, 
        db=0,
        decode_responses=True, # returns strings instead of bytes
        )
    try:
        # Test the connection at startup
        runtime_services.redis_client.ping()
    except RedisError as e: 
        logging.exception("Redis connection failed") 
        raise RuntimeError(f"redis unavailable at host: {REDIS_HOST_URL} port: {REDIS_HOST_PORT}") from e


    # Connect to Twilio
    if not TWILIO_API_KEY or not TWILIO_API_SECRET:
        raise RuntimeError("Twilio credentials missing")

    runtime_services.twilio_client = TwilioClient(TWILIO_API_KEY, TWILIO_API_SECRET)
    runtime_services.owner_phone = OWNER_PHONE
    runtime_services.caller_phone = CALLER_PHONE

    yield


    logging.info("Shutting down CanineGlucose API")

    if runtime_services.redis_client is not None:
        runtime_services.redis_client.close()
        runtime_services.redis_client = None

    runtime_services.twilio_client = None
    runtime_services.owner_phone = None
    runtime_services.caller_phone = None

    runtime_services.model_bundle = None


### Instantiate our API
app = FastAPI(lifespan=lifespan_mechanism)

# Connect to routers
app.include_router(observable_ui_router)
app.include_router(cgm_router)


### API Endpoints
@app.get("/health")
def read_health(): 
    return {"time": datetime.datetime.now().isoformat()}
