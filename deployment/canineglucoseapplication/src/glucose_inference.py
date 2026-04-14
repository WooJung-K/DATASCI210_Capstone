import logging
from redis import Redis

import src.runtime_services as runtime_services

from src.data_models.glucose_reading import GlucoseReading
from src.glucose_io import get_glucose_history_for_inference
from src.voice_alert import low_glucose_alarm, high_glucose_alarm
from model.model_inference import predict_glucose_class

logger = logging.getLogger(__name__)

def build_features(history, reading):
    pass
    # expect a list of (timestamp,value) pairs

    # check if features are complete / correct?
        # do we interpolate missing values?
        # when do we throw an error? No features?

    # compute features

    # return numpy array of transformed features

def predict(features):
    pass
    # return label

def voice_alert(twilio_client, OWNER_PHONE, CALLER_PHONE, label):
    # pass
    # low_glucose_alarm(twilio_client, OWNER_PHONE, CALLER_PHONE)
    high_glucose_alarm(twilio_client, OWNER_PHONE, CALLER_PHONE)

def run_inference_pipeline(redis_client, twilio_client, OWNER_PHONE, CALLER_PHONE, reading):
    
    # Query RedisTimeSeries for recent history
    # use key and timestamp from current reading
    history = get_glucose_history_for_inference(redis_client, reading, lookback_minutes = 60)

    # skip inference if not enough recent data
    if not history:
        logger.warning("No history for inference")
        return None


    # Build Features
    #  - Pass or fake features for now?
    # features = build_features(history)


    # Inference
    try:
        result = predict_glucose_class(
            bundle=runtime_services.model_bundle,
            readings=history,
            prediction_time=reading.DeviceTimestamp,
        )
    except Exception as e:
        logger.warning(f"Inference failed: {e}")
        return None
    
    # label = predict(features) or something like that
    label = result["predicted_class"]

    # Check if alert is needed
        # Use the history to look at previous values. Was the last one normal? Is the current label hypo/hyperglycemic?
    _, last_glucose = history[-2] # Remember -1 is the most recent reading that triggered this inference.
    last_glucose = float(last_glucose)

    # safe → unsafe transition
    logger.info(
        f"Alert decision: last_glucose={last_glucose}, "
        f"predicted_class={label}, "
        f"enable_alert_calls={runtime_services.enable_alert_calls}"
)

    if (65 <= last_glucose <= 250) and (label in {"hypoglycemia", "hyperglycemia"}):
        if runtime_services.enable_alert_calls:
            try:
                voice_alert(twilio_client, OWNER_PHONE, CALLER_PHONE, label)
            except Exception:
                logger.exception("Failed to send alert")
        else:
            logger.info(
                "Alert suppressed",
                extra={
                    "last_glucose": last_glucose,
                    "predicted_class": label,
                },
            )


    # return or write result to log