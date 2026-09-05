# Features

## 1. Live ETA prediction

Given a train's current station and delay, predicts the delay at each
upcoming station. Three parts, each doing a distinct job:

- **XGBoost residual model** (`ml/train_model.py`) — predicts the change
  in delay between now and the next station (not the absolute delay
  directly; predicting the residual on top of `delay_so_far` is more
  stable and lets the model focus on what's actually changing).
- **Asymmetric quantile confidence interval** — two extra XGBoost models
  trained with pinball loss at the 10th/90th percentiles, so the
  confidence band isn't a fixed `±margin` around every prediction. It
  widens or narrows depending on the situation (e.g. wider when
  congestion/weather make the outcome less predictable).
- **SHAP explanation** (`ml/predict.py`) — every prediction comes with a
  per-feature attribution from a `TreeExplainer` over the actual model, so
  "why does the model think this" has a real, model-grounded answer
  rather than a plausible-sounding guess.

## 2. Cross-train congestion

`ml/congestion.py` adds a feature most naive versions of this problem
miss: how many *other* trains are scheduled through the same station
within a time window, independent of the train's own simulated congestion
factor. Delay isn't just a function of one train's situation — it's also a
function of what else is competing for the same platform/section at the
same time.

## 3. Recommendation engine

`ml/recommend.py` turns a raw prediction into action: audience-tagged
(control room / station staff / passenger), priority-tagged
recommendations based on delay severity, congestion, weather, and dwell
overrun. Deliberately rules-based rather than learned — there's no ground
truth for "was this the right operational call" in synthetic data, so a
learned recommender would just fit noise. Rules are transparent, easy to
justify to a judge, and swappable for an optimization model once real
outcome data exists.

## 4. Anomaly detection

`ml/anomaly.py` uses an Isolation Forest to flag delay events whose
pattern (combination of weather/congestion/dwell/carried-over-delay)
looks statistically unusual relative to normal traffic. This is a genuine,
working component — but see `LIMITATIONS.md`: it flags outliers in
*simulated* data, and has not been validated against real rare
operational events (derailments, signal failures, major disruptions),
because no labeled real-incident dataset is available to this project.

## 5. Historical dataset model (separate from the live model, on purpose)

`ml/train_historical_model.py` trains a model directly on
`data/train_delay_data.csv` — a real uploaded historical dataset
(distance, weather, day of week, time of day, train type, route
congestion → historical delay) — completely independent of the synthetic
live-simulation dataset used everywhere else in this project.

This is deliberate, not incidental: it means there's one part of this
system that can be tested against real records in front of judges,
separately from the live demo, without either muddying the other's
story. The frontend's "Historical Dataset Test" tab exists specifically
for this.

## 6. LSTM benchmark (second model, item 5 of the roadmap)

`ml/train_lstm.py` trains an LSTM over each train's full ordered sequence
of stations-so-far, and benchmarks it against a *journey-split* XGBoost
baseline retrained inline in the same script (so the comparison is
apples-to-apples — see the file's docstring for why a fresh journey-level
split, rather than reusing `train_model.py`'s row-level split, is
necessary to make this a fair comparison and avoid leakage).

**This script has not been executed in this environment** (no GPU/heavy
`torch` install in the assistant's sandbox). Run `python ml/train_lstm.py`
yourself and treat its printed MAE/latency numbers as the real result —
nothing about its outcome is assumed or pre-filled anywhere in these docs.

## 7. SMS / push alerts

`backend/sms_provider.py` + `backend/routers/alerts.py`: a passenger (or
operator, on their behalf) subscribes a phone number to a specific train
with a delay threshold. When a live delay event pushes that train's delay
past the threshold, every matching subscription gets a message.

Two provider paths, auto-selected: a real Twilio path if Twilio
credentials are set as environment variables, and a working stub
otherwise that logs exactly what would have been sent and returns a
simulated delivery result — so the whole subscribe → delay → notify flow
is demoable end-to-end with zero external account or cost.

## 8. Auth / role-based access control

`backend/auth.py` + `backend/routers/auth.py`: JWT-based login
(`POST /auth/token`, standard OAuth2 password flow so Swagger's Authorize
button works out of the box) with three hierarchical roles:

- **viewer** — read-only (GET endpoints, subscribing your own phone to
  alerts).
- **operator** — viewer + can trigger simulated delay events, view
  subscription/alert logs.
- **admin** — operator + admin-only endpoints (e.g. listing all users).

Passwords are hashed with PBKDF2-HMAC-SHA256 (260,000 iterations, random
per-user salt) — no bcrypt/passlib dependency, since this repo already
asks a hackathon judge to install enough as it is.

## 9. Load testing

`scripts/load_test.py` hits a real running server with concurrent async
requests and reports p50/p95/p99 latency and achieved throughput — a
genuine load test, not a simulated one. It directly motivated a real fix:
the `/anomalies` endpoint was re-running a 200-tree Isolation Forest's
full scoring pass on every single request (5-9 seconds each); the load
test surfaced this, and it's now cached at startup (see
`backend/main.py`'s `_warm_caches_on_startup`).

**Also not executed in this environment** — run it against your own local
server (`uvicorn backend.main:app`) and treat its printed numbers as the
real result.

## 10. Dashboard

A single React app (`frontend/`) with two views, toggled from the top
bar:

- **Live Operations** — real trains from `/trains`, real predictions from
  `/eta/journey`, a working "Simulate delay event" button that shows the
  ETA-changed banner and recalculated recommendations live.
- **Historical Dataset Test** — a form for the historical model's six
  input fields, submits to `/historical/predict`, shows the predicted
  delay and its SHAP factor breakdown.

No hardcoded mock data — everything on screen comes from a live API call.
