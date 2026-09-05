# API Reference

Base URL (local): `http://localhost:8000`. Interactive docs (Swagger UI,
with a working "Authorize" button for the JWT flow) are auto-served at
`/docs`.

Auth notation below: **open** = no token needed, **any role** = any valid
JWT, **operator+** = operator or admin, **admin** = admin only.

## Auth

### `POST /auth/token` — open
Standard OAuth2 password flow. Form-encoded body: `username`, `password`.
```bash
curl -X POST http://localhost:8000/auth/token \
  -d "username=operator&password=operator123"
```
Returns `{ access_token, token_type: "bearer", role, username }`. Send the
token back as `Authorization: Bearer <access_token>`.

Demo accounts: `admin`/`admin123`, `operator`/`operator123`,
`viewer`/`viewer123`.

### `GET /auth/me` — any role
Returns the current user's `{ username, role, is_active }`.

### `GET /auth/users` — admin
Lists all seeded users. Exists specifically as a concrete example of an
admin-only route for the RBAC demo.

## Live ETA

### `GET /eta/predict?train_no=&current_station_code=&next_station_code=` — open
Single-station prediction. Returns `ETAResponse`: predicted delay,
asymmetric confidence interval (`confidence_lower`/`confidence_upper`),
a natural-language `explanation`, a `contributions` breakdown (ground-truth
simulated factors: weather/congestion/dwell/carried-over-delay/unscheduled
events), `shap_contributions` (what the model itself weighted), an
`eta_change` block if the prediction differs from a prior call for the
same train/station, and `recommendations`.

### `GET /eta/journey?train_no=&current_station_code=` — open
Full remaining-journey prediction in one call — one `JourneyStationPrediction`
per upcoming station, same shape as `/eta/predict`'s response fields. This
is what the dashboard's route view uses instead of one request per station.

## Trains

### `GET /trains` — open
Lists every train in the current simulated dataset: `train_no`, `route_id`,
full `stations` list (code/name/distance/sequence), and the train's
current station. Powers the dashboard's train list/sidebar.

## Simulate

### `POST /simulate/delay-event` — operator+
Body: `{ train_no, station_code, extra_minutes }`. Adds `extra_minutes` to
the most recent recorded delay for that train/station, mimicking a live
GPS/NTES update. Subsequent `/eta/predict` or `/eta/journey` calls for the
same train reflect the change and return a genuine `eta_change` block.
Also fires `notify_subscribers` (see Alerts) for anyone subscribed to that
train above the new delay threshold. Gated to `operator`+ because it
mutates shared demo state — not something a read-only viewer should
trigger.

## Anomalies

### `GET /anomalies` — open
Returns rows flagged by the Isolation Forest anomaly model as statistical
outliers: `train_no`, `route_id`, `station_code`, `day_id`,
`delay_minutes`, `anomaly_score`. See `LIMITATIONS.md` — this flags
outliers in simulated data, not validated against real rare events.

## Historical dataset model

### `GET /historical/meta` — open
Returns the categorical values the historical model was trained on
(`weather_conditions`, `day_of_week`, `time_of_day`, `train_type`,
`route_congestion`) plus `model_mae_minutes`, read live from the trained
model bundle so the frontend's dropdowns can never drift from what the
model actually knows.

### `POST /historical/predict` — open
Body: `{ distance_km, weather_conditions, day_of_week, time_of_day, train_type, route_congestion }`
(matches `data/train_delay_data.csv`'s columns exactly). Returns
`{ predicted_delay_minutes, model_mae_minutes, factors }`, where `factors`
is a SHAP-based breakdown of which inputs pushed the prediction up or down.

## Alerts

### `POST /alerts/subscribe` — any role
Body: `{ train_no, channel: "sms"|"push", destination, min_delay_minutes }`.
Registers a subscription; no special role needed since a passenger
subscribing to their own train is exactly what a `viewer` account is for.

### `DELETE /alerts/unsubscribe/{subscription_id}` — any role

### `GET /alerts/subscriptions?train_no=` — operator+
Lists active subscriptions, optionally filtered by train. Operator-only:
this is operational tooling, not passenger-facing.

### `GET /alerts/sent` — operator+
Lists every alert delivery attempt, most recent first, including which
provider handled it (`twilio` or `stub`) and whether it succeeded. Exists
to prove the pipeline actually fired during a demo, since a stub delivery
doesn't produce a real SMS to show.

## Everything else

`GET /` — open, basic health check (`{ status: "ok", message: "..." }`).
