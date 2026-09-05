# Changelog

Roughly chronological, grouped by milestone rather than by commit.

## v0 — Base project

- Synthetic data simulator (`data_simulator/simulate.py`) generating
  trains, routes, stations, and per-station delay events.
- Baseline XGBoost residual model (`ml/train_model.py`) with a fixed
  symmetric `±margin` confidence interval.
- FastAPI backend: `/eta/predict`, `/eta/journey`, `/trains`,
  `/simulate/delay-event` (no auth).

## v1 — "Tier 1" enhancements

- **Cross-train congestion** (`ml/congestion.py`) — a real feature
  counting other trains scheduled near the same station/time window,
  independent of each train's own simulated congestion factor.
- **Asymmetric quantile confidence interval** — replaced the fixed
  `±1.28×std` margin with two additional XGBoost models trained on
  pinball loss at the 10th/90th percentiles, conditioning the interval
  width on the actual situation.
- **SHAP explanations** (`ml/predict.py`) — per-prediction feature
  attribution from a `TreeExplainer` over the real fitted model.
- **Recommendation engine** (`ml/recommend.py`) — rules-based,
  audience/priority-tagged operational guidance derived from each
  prediction.
- Rebuilt the frontend dashboard to consume live API data instead of
  hardcoded mock data, matching a specific reference design.

## v2 — Historical dataset model + matching frontend tab

- Added a real uploaded historical dataset
  (`data/train_delay_data.csv`) and a completely separate training/
  inference pipeline for it (`ml/train_historical_model.py`,
  `ml/predict_historical.py`, `backend/routers/historical.py`) —
  deliberately independent of the synthetic live-simulation model.
- Added the "Historical Dataset Test" tab to the frontend so this model
  can be demoed on its own, separate from the live-operations story.
- Anomaly detection (`ml/anomaly.py`, `backend/routers/anomalies.py`)
  added around this point: Isolation Forest flagging statistical
  outliers in the synthetic dataset.

## v3 — Roadmap items 8, 5, 9, 11

Four specific roadmap items, implemented in this order:

- **Item 8 — SMS/push alerts.** `backend/sms_provider.py` (Twilio path +
  working stub), `backend/routers/alerts.py` (subscribe/unsubscribe/
  list-subscriptions/sent-log), wired into `simulate.py` so a live delay
  event fires alerts to subscribers above their threshold.
- **Item 5 — LSTM as a second model.** `ml/train_lstm.py`, benchmarked
  against a journey-split XGBoost baseline on the same held-out data to
  keep the comparison fair and leakage-free. Not yet executed in this
  environment — see `LIMITATIONS.md`.
- **Item 9 — Auth / role-based access control.** `backend/auth.py`
  (PBKDF2 password hashing, JWT issuance/verification, hierarchical
  `require_role` dependency), `backend/routers/auth.py`
  (`/auth/token`, `/auth/me`, `/auth/users`), `backend/seed.py` (seeds
  three demo accounts on startup). `simulate.py`'s delay-event endpoint
  now requires `operator`+.
- **Item 11 — Load testing.** `scripts/load_test.py`, an async load
  tester against a real running server reporting p50/p95/p99 latency and
  throughput. Not yet executed in this environment — see
  `LIMITATIONS.md`. Its design directly informed a real performance fix:
  `/anomalies`' Isolation Forest scoring is now cached at startup
  (`backend/main.py`'s `_warm_caches_on_startup`) instead of recomputed
  per request, after this class of cold-cache cost was identified as the
  likely worst-case bottleneck under concurrent load.

## v4 — Visual + documentation pass (this version)

- Increased color saturation/contrast across the dashboard (brighter
  brand blue, greens, oranges, reds; crisp white panels replacing the
  earlier washed grey-blue) while keeping the overall light theme and
  layout unchanged.
- Full rewrite of every file in `docs/` (this file included) to reflect
  the complete current feature set, architecture, API surface, tech
  stack, setup instructions, and an honest limitations account
  distinguishing validated / demoable-but-unvalidated / not-yet-run /
  structurally-out-of-reach components.

## Not yet started

Roadmap items 7 (passenger mobile view), 6 (already partially covered by
the anomaly detector, but full "rare event" scope remains open), and 4
(multi-route expansion beyond the current simulated corridors).
