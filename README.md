# RailPulse — Dynamic ETA Prediction for Indian Railways

RailPulse is a live prediction system for Smart India Hackathon problem
statement 26028: given a train's live state, predict what will actually
happen at its next stations — not just "on time / late" but a delay in
minutes, a confidence band around it, why the model thinks that, and what
to do about it.

This repo contains a working ETA prediction API, a live-operations
dashboard, a separate model tested against a real historical dataset,
anomaly detection, SMS/push alerting, role-based access control, and an
LSTM benchmark — all runnable locally.

## What's actually in here

| Area | What it does | Where |
|---|---|---|
| Live ETA model | XGBoost residual model + asymmetric quantile confidence interval + SHAP explanation per prediction | `ml/train_model.py`, `ml/predict.py` |
| Cross-train congestion | Real feature: how many other trains are scheduled through the same station/time window | `ml/congestion.py` |
| Recommendation engine | Rules-based operational guidance (control room / station staff / passenger) derived from each prediction | `ml/recommend.py` |
| Anomaly detection | Isolation Forest flagging statistically unusual delay patterns | `ml/anomaly.py`, `backend/routers/anomalies.py` |
| Historical dataset model | Separate model trained on a real uploaded CSV (`data/train_delay_data.csv`), independent of the synthetic live model | `ml/train_historical_model.py`, `backend/routers/historical.py` |
| LSTM benchmark | Second model architecture, benchmarked against XGBoost on the same journey-split held-out data | `ml/train_lstm.py` |
| SMS/push alerts | Subscribe a phone number to a train; a live delay event pushes a message (Twilio if configured, working stub otherwise) | `backend/sms_provider.py`, `backend/routers/alerts.py` |
| Auth / RBAC | JWT-based login, three roles (viewer/operator/admin), enforced on write endpoints | `backend/auth.py`, `backend/routers/auth.py` |
| Load testing | Async load-test script against a real running server, reports p50/p95/p99 latency and throughput | `scripts/load_test.py` |
| Dashboard | React app: live operations view + a separate historical-dataset test tab | `frontend/` |

See `docs/` for the full breakdown of each piece: `FEATURES.md` (what
each feature does and why), `ARCHITECTURE.md` (how it fits together),
`API.md` (every endpoint), `TECH_STACK.md`, `SETUP.md` (how to run it),
`LIMITATIONS.md` (what's honestly not validated yet), and
`CHANGELOG.md` (how it got here).

## Quick start

```bash
pip install -r requirements.txt

python ml/train_model.py               # live ETA + anomaly models
python ml/train_historical_model.py    # historical CSV model
python ml/train_lstm.py                # optional: LSTM benchmark (requires torch)

uvicorn backend.main:app --reload      # API on http://localhost:8000

cd frontend && npm install && npm run dev   # dashboard on http://localhost:5173
```

Demo login (for RBAC-protected endpoints and the dashboard): `admin` /
`admin123`, `operator` / `operator123`, `viewer` / `viewer123`. Full detail
in `docs/SETUP.md`.

## What this is not (yet)

This runs entirely on synthetic simulated data for the live model (real
NTES/CRIS data access isn't something a hackathon team can obtain), and the
anomaly detector isn't validated against real incident data. The
historical-dataset model is the one component tested against real records.
See `docs/LIMITATIONS.md` for the full, honest list — the numbers in this
repo are real results from real runs, not invented figures, but the scope
they're real *within* matters.
