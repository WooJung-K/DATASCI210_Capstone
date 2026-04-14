from __future__ import annotations

import pickle
from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd


@dataclass
class InferenceBundle:
    model: object
    label_encoder: object
    feature_cols: list[str]
    history_minutes: int
    ahead_minutes: int


def load_inference_bundle(path: str) -> InferenceBundle:
    with open(path, "rb") as f:
        bundle = pickle.load(f)

    config = bundle["config"]

    return InferenceBundle(
        model=bundle["model"],
        label_encoder=bundle["label_encoder"],
        feature_cols=bundle["feature_cols"],
        history_minutes=config["history_minutes"],
        ahead_minutes=config["ahead_minutes"],
    )


def build_readings_df(
    readings: Iterable[tuple[int, float]] | Iterable[tuple[pd.Timestamp, float]]
) -> pd.DataFrame:
    """
    readings:
      - either (timestamp_ms, glucose)
      - or (timestamp, glucose)

    Returns a dataframe with columns:
      timestamp (UTC pandas Timestamp)
      glucose (float)
    """
    rows = []
    for ts, glucose in readings:
        if isinstance(ts, (int, np.integer)):
            timestamp = pd.to_datetime(ts, unit="ms", utc=True)
        else:
            timestamp = pd.to_datetime(ts, utc=True)

        rows.append({"timestamp": timestamp, "glucose": float(glucose)})

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError("No readings provided")

    df = (
        df.dropna(subset=["timestamp", "glucose"])
          .sort_values("timestamp")
          .drop_duplicates(subset=["timestamp"], keep="last")
          .reset_index(drop=True)
    )

    return df


def resample_to_minute_grid(
    df: pd.DataFrame,
    prediction_time: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """
    Create 1-minute glucose series with linear interpolation.
    No AR noise is added.
    """
    if prediction_time is None:
        prediction_time = pd.Timestamp.utcnow().tz_localize("UTC") if pd.Timestamp.utcnow().tzinfo is None else pd.Timestamp.utcnow()

    prediction_time = pd.to_datetime(prediction_time, utc=True).floor("min")

    d = df.copy().set_index("timestamp").sort_index()

    start = d.index.min().floor("min")
    end = prediction_time

    full_index = pd.date_range(start=start, end=end, freq="1min", tz="UTC")
    minute_df = d.reindex(full_index)

    minute_df["glucose"] = minute_df["glucose"].interpolate(
        method="time",
        limit_area="inside",
    )

    minute_df = minute_df.reset_index().rename(columns={"index": "timestamp"})

    return minute_df


def extract_feature_row(
    minute_df: pd.DataFrame,
    prediction_time: pd.Timestamp,
    history_minutes: int = 30,
    ahead_minutes: int = 15,
) -> pd.DataFrame:
    """
    Build the exact feature vector expected by the trained model.

    For prediction at time t:
      history window is [t-(history+ahead), t-ahead)
    """
    prediction_time = pd.to_datetime(prediction_time, utc=True).floor("min")

    hist_end = prediction_time - pd.Timedelta(minutes=ahead_minutes)
    hist_start = hist_end - pd.Timedelta(minutes=history_minutes)

    window = minute_df[
        (minute_df["timestamp"] >= hist_start) &
        (minute_df["timestamp"] < hist_end)
    ].copy()

    expected_rows = history_minutes
    if len(window) != expected_rows:
        raise ValueError(
            f"Insufficient minute-level history. Expected {expected_rows} rows, got {len(window)}."
        )

    if window["glucose"].isna().any():
        raise ValueError("History window contains NaN glucose values after interpolation.")

    g = window["glucose"].to_numpy(dtype=float)

    first_glucose = g[0]
    last_glucose = g[-1]

    feature_row = pd.DataFrame([{
        "mean_glucose": float(np.mean(g)),
        "min_glucose": float(np.min(g)),
        "max_glucose": float(np.max(g)),
        "slope": float((last_glucose - first_glucose) / history_minutes),
        "last_glucose": float(last_glucose),
    }])

    return feature_row


def predict_glucose_class(
    bundle: InferenceBundle,
    readings: Iterable[tuple[int, float]] | Iterable[tuple[pd.Timestamp, float]],
    prediction_time: Optional[pd.Timestamp] = None,
) -> dict:
    """
    End-to-end live inference from recent readings.
    """
    if prediction_time is None:
        prediction_time = pd.Timestamp.now(tz="UTC").floor("min")
    else:
        prediction_time = pd.to_datetime(prediction_time, utc=True).floor("min")

    observed_df = build_readings_df(readings)
    minute_df = resample_to_minute_grid(observed_df, prediction_time=prediction_time)

    feature_row = extract_feature_row(
        minute_df=minute_df,
        prediction_time=prediction_time,
        history_minutes=bundle.history_minutes,
        ahead_minutes=bundle.ahead_minutes,
    )

    X = feature_row[bundle.feature_cols]

    pred_encoded = bundle.model.predict(X)[0]
    pred_label = bundle.label_encoder.inverse_transform([pred_encoded])[0]

    output = {
        "prediction_time": prediction_time.isoformat(),
        "predicted_class": pred_label,
        "features": feature_row.iloc[0].to_dict(),
    }

    if hasattr(bundle.model, "predict_proba"):
        probs = bundle.model.predict_proba(X)[0]
        class_labels = list(bundle.label_encoder.classes_)
        output["class_probabilities"] = {
            class_labels[i]: float(probs[i]) for i in range(len(class_labels))
        }

    return output