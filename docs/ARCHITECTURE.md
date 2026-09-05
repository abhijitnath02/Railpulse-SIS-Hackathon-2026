# Architecture

## Overview

```
data_simulator/simulate.py          backend/database.py (SQLite, via SQLAlchemy)
        │                                   │
        ▼                                   ▼
data/train_events.csv          Users, AlertSubscriptions, SentAlerts
        │
        ▼
ml/features.py  ── build_feature_table() ──┐
        │  (+ ml/congestion.py)            │
        ▼                                  │
ml/train_model.py  ──►  models/eta_residual_model.pkl
ml/anomaly.py      ──►  models/anomaly_model.pkl        │
                                                          │
data/train_delay_data.csv (real historical dataset)      │
        │                                                 │
        ▼                                                 │
ml/train_historical_model.py ──► models/historical_delay_model.pkl
                                                          │
                                                          ▼
                                            backend/routers/*.py
                                            (eta, trains, simulate, anomalies,
                                             historical, auth, alerts)
                                                          │
                                                          ▼
                                                  backend/main.py (FastAPI)
                                                          │
                                                          ▼
                                              frontend/ (React dashboard)
```

## Live prediction flow (the core loop)

1. `data_simulator/simulate.py` generates a synthetic dataset of trains,
   routes, stations, and per-station events (weather/congestion/dwell
   factors, delay minutes) into `data/train_events.csv`.
2. `ml/features.py` builds the model's feature table from that raw data —
   historical averages, delay-so-far, and (via `ml/congestion.py`) the
   cross-train congestion count.
3. `ml/train_model.py` trains three XGBoost models on this feature table:
   the main residual predictor, and two quantile models (10th/90th
   percentile) for the confidence interval. Also trains the Isolation
   Forest anomaly model.
4. At request time, `backend/routers/eta.py` loads the cached feature
   table, builds one row for the requested train/station, and calls
   `ml/predict.py`, which runs all three models plus a SHAP
   `TreeExplainer` and returns a prediction with an asymmetric interval
   and per-feature attribution.
5. `ml/recommend.py` turns that prediction into rules-based
   recommendations, attached to the same response.
6. `backend/routers/simulate.py` lets a client (the dashboard's "Simulate
   delay event" button, gated to `operator`+ role) mutate the live feature
   table's delay value for one train/station — this is the "GPS/NTES
   update just came in" step in a real system, faked here since no real
   feed is available. `eta.py` detects the resulting change and returns an
   `eta_change` block, and `backend/routers/alerts.py`'s
   `notify_subscribers` fires SMS/push alerts to anyone subscribed above
   the new delay threshold.

## The historical model is a separate, parallel pipeline

`data/train_delay_data.csv` → `ml/train_historical_model.py` →
`models/historical_delay_model.pkl` → `backend/routers/historical.py` is
intentionally not connected to the pipeline above. It answers a different
question ("what does real history say to expect under these conditions")
using a real dataset, rather than the live simulator's synthetic one. The
frontend keeps them in separate tabs for the same reason.

## Caching

Two things are expensive to recompute per-request and don't change
between requests within a demo session: the built feature table
(`get_feature_table()` in `eta.py`) and the anomaly model's scored output
(`_get_scored()` in `anomalies.py`, which runs Isolation Forest scoring
over the whole table). Both are cached at process startup
(`backend/main.py`'s `_warm_caches_on_startup`) after `scripts/load_test.py`
showed the cold-cache cost was severe (5-12s) under concurrent load even
with a lock preventing duplicate recomputation — warming at startup means
no real request ever pays that cost.

## Auth layering

`backend/auth.py` provides `get_current_user` (any valid JWT) and
`require_role(minimum)` (hierarchical role check) as FastAPI dependencies.
Routers apply them per-endpoint: read endpoints are open or
`get_current_user`-gated, `simulate.py`'s delay-event endpoint requires
`operator`, and `auth.py`'s `/auth/users` requires `admin`. Users live in
the same SQLite database as everything else (`backend/models.py`'s `User`
table), seeded on startup by `backend/seed.py`.
