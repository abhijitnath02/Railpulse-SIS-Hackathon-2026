"""
Loads the trained residual model and produces a final ETA prediction:

    final_delay = baseline_delay (delay_so_far) + predicted_residual

Returns a point estimate plus a confidence interval derived from the
model's historical residual error spread.
"""
from pathlib import Path
from dataclasses import dataclass

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "eta_residual_model.pkl"

_bundle = None


def _load_bundle():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


@dataclass
class ETAPrediction:
    predicted_delay_minutes: float
    lower_bound_minutes: float
    upper_bound_minutes: float


def predict_delay(feature_row: dict) -> ETAPrediction:
    """
    feature_row must contain: distance_km, hour_of_day, station_seq,
    weather_factor, congestion_factor, historical_avg_delay, delay_so_far
    """
    bundle = _load_bundle()
    model = bundle["model"]
    error_std = bundle["error_std"]
    features = bundle["features"]

    X = pd.DataFrame([feature_row])[features]
    residual_pred = float(model.predict(X)[0])

    final_delay = feature_row["delay_so_far"] + residual_pred
    final_delay = max(0.0, final_delay)  # delay can't be negative

    margin = 1.28 * error_std  # ~80% confidence band, adjust as needed
    lower = max(0.0, final_delay - margin)
    upper = final_delay + margin

    return ETAPrediction(
        predicted_delay_minutes=round(final_delay, 1),
        lower_bound_minutes=round(lower, 1),
        upper_bound_minutes=round(upper, 1),
    )
