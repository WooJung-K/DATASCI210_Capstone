from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.glucose_api import app as glucose_prediction, lifespan_mechanism


@asynccontextmanager
async def main_lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        # Manage the lifecycle of sub_app
        await stack.enter_async_context(
            lifespan_mechanism(glucose_prediction)
        )
        yield


app = FastAPI(lifespan=main_lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # tighten this later
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create and Mount glucose prediction endpoint
app.mount("/woof", glucose_prediction)




### TO DO List ###

# Connect to Redis instance
# Write to RedisTimeSeries

# Query RedisTimeSeries for recent history

# Build Features
#  - Pass or fake features for now?

# Inference
# - Load Model
# - Run Inference on Features
# - Log Prediction (required for safe -> unsafe trigger)

# Send SMS if safe -> unsafe

# Return prediction
