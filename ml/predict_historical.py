"""
Inference for the historical delay model (see train_historical_model.py
for what this model is and why it's kept separate from the live ETA model).
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "historical_delay_model.pkl"

_bundle = None
_explainer = None


def _load_bundle():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def get_category_options() -> dict:
    return _load_bundle()["category_options"]


@dataclass
class HistoricalFactor:
    feature: str
    value: str
    impact_minutes: float


@dataclass
class HistoricalPrediction:
    predicted_delay_minutes: float
    model_mae_minutes: float
    factors: List[HistoricalFactor] = field(default_factory=list)


def predict_historical_delay(input_row: dict) -> HistoricalPrediction:
    """
    input_row keys: 'Distance Between Stations (km)', 'Weather Conditions',
    'Day of the Week', 'Time of Day', 'Train Type', 'Route Congestion'
    """
    bundle = _load_bundle()
    model = bundle["model"]
    X = pd.DataFrame([input_row])[bundle["numeric_features"] + bundle["categorical_features"]]

    pred = float(model.predict(X)[0])
    pred = max(0.0, pred)

    # SHAP over the fitted XGBoost step, run on the one-hot-encoded matrix
    # the regressor actually sees, then collapsed back to the original
    # human-readable feature names (e.g. all "Weather Conditions=Rainy"
    # columns collapse into one "Weather Conditions" contribution) so the
    # explanation matches what the user actually input.
    global _explainer
    import shap
    preprocessor = model.named_steps["preprocess"]
    regressor = model.named_steps["regressor"]
    X_enc = preprocessor.transform(X)
    if hasattr(X_enc, "toarray"):
        X_enc = X_enc.toarray()

    if _explainer is None:
        _explainer = shap.TreeExplainer(regressor)
    shap_values = _explainer.shap_values(X_enc)[0]

    enc_feature_names = preprocessor.get_feature_names_out()
    contrib_by_original: dict = {}
    for name, val in zip(enc_feature_names, shap_values):
        # name looks like "cat__Weather Conditions_Rainy" or "remainder__Distance..."
        original = name.split("__", 1)[-1]
        for cat_feat in bundle["categorical_features"]:
            if original.startswith(cat_feat + "_"):
                original = cat_feat
                break
        contrib_by_original[original] = contrib_by_original.get(original, 0.0) + float(val)

    factors = [
        HistoricalFactor(
            feature=bundle["numeric_features"][0] if feat not in bundle["categorical_features"] else feat,
            value=str(input_row.get(feat, input_row.get(bundle["numeric_features"][0], ""))),
            impact_minutes=round(v, 1),
        )
        for feat, v in contrib_by_original.items()
    ]
    factors.sort(key=lambda f: abs(f.impact_minutes), reverse=True)

    return HistoricalPrediction(
        predicted_delay_minutes=round(pred, 1),
        model_mae_minutes=round(bundle["mae"], 1),
        factors=factors,
    )
