"""
Loads the trained residual model and produces a final ETA prediction:

    final_delay = baseline_delay (delay_so_far) + predicted_residual

Returns a point estimate plus a confidence interval derived from the
model's historical residual error spread.
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "eta_residual_model.pkl"

_bundle = None
_explainer = None


def _load_bundle():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def _load_explainer(model):
    """SHAP TreeExplainer is cheap to construct for tree models (no
    background dataset needed) but importing shap has a noticeable cost, so
    it's deferred and cached until the first prediction actually needs it."""
    global _explainer
    if _explainer is None:
        import shap
        _explainer = shap.TreeExplainer(model)
    return _explainer


@dataclass
class FeatureContribution:
    feature: str
    value: float
    shap_minutes: float  # signed contribution to the predicted RESIDUAL, in minutes


@dataclass
class ETAPrediction:
    predicted_delay_minutes: float
    lower_bound_minutes: float
    upper_bound_minutes: float
    shap_contributions: List[FeatureContribution] = field(default_factory=list)


def predict_delay(feature_row: dict, explain: bool = True) -> ETAPrediction:
    """
    feature_row must contain: distance_km, hour_of_day, station_seq,
    weather_factor, congestion_factor, cross_train_congestion,
    historical_avg_dwell, historical_avg_delay, delay_so_far
    """
    bundle = _load_bundle()
    model = bundle["model"]
    features = bundle["features"]

    X = pd.DataFrame([feature_row])[features]
    residual_pred = float(model.predict(X)[0])

    final_delay = feature_row["delay_so_far"] + residual_pred
    final_delay = max(0.0, final_delay)  # delay can't be negative

    # --- Asymmetric, feature-conditioned confidence interval ---
    # Falls back to the old symmetric error_std margin if the currently
    # loaded model bundle predates the quantile models (older .pkl on disk).
    if "lower_model" in bundle and "upper_model" in bundle:
        lower_residual = float(bundle["lower_model"].predict(X)[0])
        upper_residual = float(bundle["upper_model"].predict(X)[0])
        lower = max(0.0, feature_row["delay_so_far"] + lower_residual)
        upper = max(lower, feature_row["delay_so_far"] + upper_residual)
    else:
        margin = 1.28 * bundle["error_std"]
        lower = max(0.0, final_delay - margin)
        upper = final_delay + margin

    # --- SHAP: which features actually drove this specific residual ---
    shap_contributions: List[FeatureContribution] = []
    if explain:
        explainer = _load_explainer(model)
        shap_values = explainer.shap_values(X)[0]
        for feat_name, value, shap_val in zip(features, X.iloc[0].tolist(), shap_values):
            shap_contributions.append(FeatureContribution(
                feature=feat_name,
                value=round(float(value), 2),
                shap_minutes=round(float(shap_val), 2),
            ))
        # Largest absolute contribution first, so callers can just take top-N.
        shap_contributions.sort(key=lambda c: abs(c.shap_minutes), reverse=True)

    return ETAPrediction(
        predicted_delay_minutes=round(final_delay, 1),
        lower_bound_minutes=round(lower, 1),
        upper_bound_minutes=round(upper, 1),
        shap_contributions=shap_contributions,
    )
