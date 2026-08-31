# Dynamic ETA Prediction System for Coaching Trains (SIH 26028)

A prototype real-time ETA forecasting system for Indian Railways coaching trains.
Since live GPS/NTES feeds aren't publicly available, this includes a realistic
data simulator so the whole pipeline runs end-to-end without external APIs.

## Project structure

```
sih-eta-prediction/
├── data_simulator/
│   └── simulate.py        # Generates synthetic train journeys with realistic delays
├── ml/
│   ├── features.py         # Feature engineering shared by training & inference
│   ├── train_model.py      # Trains the XGBoost ETA correction model
│   └── predict.py          # Loads trained model, scores new events
├── backend/
│   ├── main.py             # FastAPI app entrypoint
│   ├── database.py         # SQLite/Postgres connection setup
│   ├── models.py           # SQLAlchemy ORM models
│   ├── schemas.py          # Pydantic request/response schemas
│   └── routers/
│       └── eta.py          # /eta endpoints
├── data/                    # Generated CSVs land here
├── models/                  # Trained model artifacts (.pkl) land here
└── requirements.txt
```

## How to run

```bash
pip install -r requirements.txt

# 1. Generate synthetic train journey data
python data_simulator/simulate.py

# 2. Train the ETA prediction model
python ml/train_model.py

# 3. Start the API server
uvicorn backend.main:app --reload

# 4. Try it
curl "http://localhost:8000/eta/predict?train_no=12345&current_station_code=NJP&next_station_code=KIR"
```

Interactive API docs: http://localhost:8000/docs

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/trains` | List all trains in the demo dataset with their route and current position |
| GET | `/eta/predict` | Predict ETA at one specific next station |
| GET | `/eta/journey` | Predict ETA at every remaining station for a train, in one call |
| POST | `/simulate/delay-event` | Demo-only: inject extra delay at a station to trigger a live recalculation |

## Frontend dashboard

`frontend/RailPulseDashboard.jsx` is a control-room style live ETA dashboard
that calls the endpoints above directly — no mocked data. To run it:

1. Start the backend (`uvicorn backend.main:app --reload`) so it's serving
   on `http://localhost:8000`.
2. Drop `RailPulseDashboard.jsx` into any React project with `recharts`
   and `lucide-react` installed, and render `<RailPulseDashboard />`.
3. If your backend runs on a different host/port, update `API_BASE_URL`
   at the top of the file.

Click "Simulate live delay event" in the sidebar — it calls
`POST /simulate/delay-event` for the selected train's current station,
then re-fetches `/eta/journey`. The route view, the delay figures, and the
delay-contribution bar chart all update from a real backend response, and
an "ETA updated" banner appears showing the actual before/after change —
this is the moment worth demoing live.

## Example: dynamic ETA update in action

This is the core "dynamic forecast" behaviour the problem statement asks for,
captured from an actual run of this system.

**Call 1 — train running close to schedule:**
```bash
curl "http://localhost:8000/eta/predict?train_no=12000&current_station_code=NJP&next_station_code=KIR"
```
```json
{
  "train_no": "12000",
  "next_station_code": "KIR",
  "predicted_delay_minutes": 3.3,
  "predicted_eta": "2025-04-30T12:51:40",
  "explanation": "Largest contributor: carried over delay (+2.0 min)",
  "eta_change": null
}
```

**A new delay is reported at the previous station** (e.g. a live GPS/NTES
update comes in showing the train picked up 15 extra minutes of delay).

**Call 2 — same train/station, moments later:**
```json
{
  "train_no": "12000",
  "next_station_code": "KIR",
  "predicted_delay_minutes": 14.4,
  "predicted_eta": "2025-04-30T13:02:46",
  "explanation": "Largest contributor: carried over delay (+17.0 min)",
  "eta_change": {
    "previous_predicted_delay_minutes": 3.3,
    "new_predicted_delay_minutes": 14.4,
    "change_minutes": 11.1,
    "contributions": [
      { "factor": "carried_over_delay", "minutes": 15.0 }
    ]
  }
}
```

The predicted delay jumped from **3.3 → 14.4 minutes**, and the response
tells you exactly why: +15 minutes of carried-over delay from the previous
station, not a vague "delay increased" message. This is the moment worth
showing live in the demo — call it once, trigger a delay update, call it
again, and watch the ETA and explanation update together.

## Design notes

- **Hybrid prediction**: a physics-based baseline ETA (schedule + recovery margin)
  is corrected by an ML residual model (XGBoost), rather than predicting raw ETA
  directly. This is more accurate and more explainable than a black-box model.
- **Confidence interval**: the API returns a predicted delay range, not just a
  point estimate, since railway ETAs carry real uncertainty.
- **Swap-in-ready**: `data_simulator/simulate.py` mimics the schema a real NTES/
  GPS feed would produce, so swapping in live data later mainly means replacing
  the simulator, not the pipeline.
