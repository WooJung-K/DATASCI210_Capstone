import datetime


def glucose_label(glucose_value: int) -> str:
    """
    Apply label to glucose reading. (Helper function for d3 observable endpoints)
    """
    if glucose_value < 65:
        return "hypoglycemia"
    if glucose_value > 250:
        return "hyperglycemia"
    return "normal"


def ms_to_datetime_utc(timestamp_ms: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=datetime.timezone.utc)


def format_range_points(redis_points: list) -> list[dict]:
    formatted = []

    for ts_ms, glucose in redis_points:
        glucose_int = int(float(glucose))
        formatted.append(
            {
                "timestamp": ms_to_datetime_utc(ts_ms),
                "glucose": glucose_int,
                "label": glucose_label(glucose_int),
                "predicted_label_10m": None,  # fill in later if/when predictions exist
            }
        )

    return formatted


def format_latest_point(redis_point) -> dict | None:
    if not redis_point:
        return None

    ts_ms, glucose = redis_point
    glucose_int = int(float(glucose))

    return {
        "timestamp": ms_to_datetime_utc(ts_ms),
        "glucose": glucose_int,
        "label": glucose_label(glucose_int),
        "predicted_label_10m": None,
    }