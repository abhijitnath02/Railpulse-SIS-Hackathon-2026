"""
Trains an XGBoost model to predict the RESIDUAL delay on top of a simple
baseline (delay carries over from the last known station). This hybrid
"physics baseline + ML correction" setup is more accurate and more
explainable than predicting raw delay from scratch.

Run: python ml/train_model.py
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from features import build_feature_table, FEATURE_COLUMNS, TARGET_COLUMN

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "train_events.csv"
MODEL_PATH = ROOT / "models" / "eta_residual_model.pkl"


def main():
    df = pd.read_csv(DATA_PATH, parse_dates=["scheduled_time", "actual_time"])
    df = build_feature_table(df)

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)

    # Compare against the naive baseline (residual = 0, i.e. "delay stays the same")
    baseline_mae = mean_absolute_error(y_test, np.zeros_like(y_test))
    model_mae = mean_absolute_error(y_test, preds)

    print(f"Naive baseline MAE (residual=0):   {baseline_mae:.2f} min")
    print(f"XGBoost residual model MAE:        {model_mae:.2f} min")
    print(f"Improvement over naive baseline:   {(1 - model_mae / baseline_mae) * 100:.1f}%")

    # Estimate a simple symmetric confidence band from residual std of test errors
    residual_errors = y_test.values - preds
    error_std = float(np.std(residual_errors))
    print(f"Residual error std (for confidence interval): {error_std:.2f} min")

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"model": model, "error_std": error_std, "features": FEATURE_COLUMNS}, MODEL_PATH)
    print(f"Saved model -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
