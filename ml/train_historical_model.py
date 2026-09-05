"""
Historical delay model — trained on a separate, real historical dataset
(data/train_delay_data.csv) rather than the synthetic simulator used by the
live-operations demo (ml/train_model.py / data/train_events.csv).

This is intentionally a SEPARATE model and a SEPARATE code path from the
live ETA model. The two demos answer different questions:
  - Live ETA model:      "given this train's live state, what will happen
                          at the next station?" (synthetic, dynamic)
  - Historical delay model: "given typical route/weather/traffic
                          conditions, what does history say to expect?"
                          (a static, tabular regression, run on demand
                          against a real uploaded dataset)

Run standalone: python ml/train_historical_model.py
Saves: models/historical_delay_model.pkl
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "train_delay_data.csv"
MODEL_PATH = ROOT / "models" / "historical_delay_model.pkl"

NUMERIC_FEATURES = ["Distance Between Stations (km)"]
CATEGORICAL_FEATURES = [
    "Weather Conditions",
    "Day of the Week",
    "Time of Day",
    "Train Type",
    "Route Congestion",
]
TARGET = "Historical Delay (min)"


def load_category_options() -> dict:
    """Distinct values for each categorical field, read straight from the
    dataset, so the frontend's dropdowns never drift out of sync with what
    the model was actually trained on."""
    df = pd.read_csv(DATA_PATH)
    return {col: sorted(df[col].dropna().unique().tolist()) for col in CATEGORICAL_FEATURES}


def train_historical_model() -> dict:
    df = pd.read_csv(DATA_PATH)
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    preprocessor = ColumnTransformer(transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ], remainder="passthrough")

    model = Pipeline(steps=[
        ("preprocess", preprocessor),
        ("regressor", XGBRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
        )),
    ])
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    baseline_mae = mean_absolute_error(y_test, np.full_like(y_test, y_train.mean(), dtype=float))

    print(f"Historical model — mean-baseline MAE: {baseline_mae:.2f} min")
    print(f"Historical model — XGBoost MAE:        {mae:.2f} min")
    print(f"Improvement over mean baseline:        {(1 - mae / baseline_mae) * 100:.1f}%")

    bundle = {
        "model": model,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "category_options": load_category_options(),
        "mae": float(mae),
    }
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    print(f"Saved historical model -> {MODEL_PATH}")
    return bundle


if __name__ == "__main__":
    train_historical_model()
