"""
Anomaly detection for rare delay events.

Flags rows whose delay pattern looks statistically unusual relative to the
rest of the dataset (e.g. an unusually large weather/congestion/dwell/random
delay combination) using an Isolation Forest — an unsupervised model that
isolates outliers without needing labeled "this was a rare event" data,
which we don't have.

IMPORTANT SCOPE NOTE: this detects statistical outliers in SIMULATED data.
It is a working, demoable component, but it has NOT been validated against
real rare operational events (derailments, signal failures, major weather
disruptions) because no real incident-labeled dataset is available in this
project. Treat its output as "this looks unusual compared to normal traffic
on this route" rather than a calibrated real-world incident detector.

Run standalone: python ml/anomaly.py  (trains and saves models/anomaly_model.pkl)
"""
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "train_events.csv"
MODEL_PATH = ROOT / "models" / "anomaly_model.pkl"

# Features describing the SHAPE of a delay event (not raw identifiers),
# so the model learns "this combination of delay causes is unusual"
# rather than memorizing which train/station it came from.
ANOMALY_FEATURES = [
    "delay_minutes",
    "weather_delay_contrib",
    "congestion_delay_contrib",
    "dwell_extra_minutes",
    "random_event_delay_contrib",
]


def train_anomaly_model(df: pd.DataFrame, contamination: float = 0.03) -> IsolationForest:
    """contamination = expected fraction of rows that are rare/outlier
    events. 0.03 (~3%) is a reasonable starting point for a demo; tune
    based on how many flagged events feel meaningful once you inspect them."""
    X = df[ANOMALY_FEATURES]
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
    )
    model.fit(X)

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"model": model, "features": ANOMALY_FEATURES}, MODEL_PATH)
    return model


_bundle = None


def _load_bundle():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def score_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Adds `anomaly_score` (higher = more anomalous) and `is_anomaly`
    (bool) columns to a copy of df."""
    bundle = _load_bundle()
    model, feats = bundle["model"], bundle["features"]

    out = df.copy()
    out["anomaly_score"] = -model.decision_function(out[feats])
    out["is_anomaly"] = model.predict(out[feats]) == -1
    return out


def main():
    df = pd.read_csv(DATA_PATH)
    model = train_anomaly_model(df)
    scored = score_anomalies(df)

    n_flagged = int(scored["is_anomaly"].sum())
    print(f"Trained Isolation Forest on {len(df)} rows, flagged {n_flagged} as anomalous")
    print(f"Saved model -> {MODEL_PATH}")

    top = scored.sort_values("anomaly_score", ascending=False).head(5)
    print("\nTop 5 most anomalous events:")
    print(top[["route_id", "train_no", "station_code", "day_id", "delay_minutes", "anomaly_score"]])


if __name__ == "__main__":
    main()
