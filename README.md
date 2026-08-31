# RailPulse — Dynamic ETA Prediction System for Coaching Trains

**Smart India Hackathon 2026 — Problem Statement 26028**  
**Team: Data Dynamos**

## Overview

RailPulse is a prototype real-time ETA forecasting system for Indian Railways coaching trains. It combines a schedule/physics-based baseline with an XGBoost residual correction model to continuously update train arrival estimates using current delay, congestion, weather, historical patterns, and operational features.

Because live GPS/NTES feeds are not publicly available for prototyping, the project includes a realistic synthetic-data simulator. The simulator follows an NTES/GPS-style data structure so the complete pipeline can run end-to-end and can later be connected to real railway data without redesigning the core prediction pipeline.

## Problem

Static or schedule-oriented ETA information does not sufficiently predict how an existing delay will affect upcoming stations. Delays can propagate because of carried-over delay, congestion, signal/operational halts, weather, dwell-time variation, and cascading effects.

RailPulse addresses this gap by answering three questions:

1. When is the train expected to reach the next stations?
2. How uncertain is that prediction?
3. Why did the ETA change?

## Objectives

- Predict ETA dynamically for upcoming stations.
- Use current operational conditions instead of relying only on timetable values.
- Combine a domain-grounded baseline with machine-learning correction.
- Provide an uncertainty range instead of only a single point estimate.
- Explain major contributors to ETA changes.
- Serve predictions through an API.
- Support passengers, station staff, and control-room users.
- Keep the architecture ready for real railway feeds.

## Research

The project studied NTES to understand existing train-status and passenger information. Research literature on real-time train-delay prediction using machine learning was reviewed to understand how ML can identify delay patterns. An India-specific study on weather and train delays supported including weather as a prediction factor.

Technical implementation was guided by XGBoost documentation for the ML correction model and FastAPI documentation for the API-serving layer.

The research led to a hybrid design: **physics/schedule baseline + ML residual correction + uncertainty + explanation**.

## Existing Infrastructure and Data Strategy

The design considers existing railway location infrastructure such as GPS/RTIS-style feeds. The objective is not to introduce new hardware or sensors, but to consume an appropriate existing operational data feed when access is available.

For the hackathon prototype, synthetic data is used because live railway feeds are not publicly available.

```text
Prototype:
Simulator → Feature Pipeline → Model → API

Production:
Approved Railway Feed → Same Feature Pipeline → Retrained Model → Same API
```

## Solution Architecture

```text
Data Sources
    ↓
Stream / Batch Ingestion
    ↓
Storage
    ↓
Feature Engineering
    ↓
Physics/Schedule Baseline
    ↓
XGBoost Residual Correction
    ↓
ETA + Delay Range + Explanation
    ↓
FastAPI
    ↓
Passenger App / Station Display / Control Room / Integrations
```

### Data Sources

- Train GPS/location pings
- Congestion or section-block information
- Weather data
- Static schedules
- Station and route information
- Historical delay logs

### Feature Engineering

The model can use:

- Current delay
- Distance/time to next station
- Historical average delay
- Congestion index
- Weather factor
- Station dwell time
- Time of day
- Seasonal effects
- Upstream delay/congestion

Historical averages are designed to avoid leakage by using information available before the current event.

## Hybrid Prediction Model

RailPulse first calculates a baseline ETA using schedule information, recovery margin, and delay already carried by the train.

XGBoost then predicts the residual correction:

```text
Residual = Actual Delay − Baseline Delay

Final prediction = Baseline + ML correction
```

This makes the learning problem smaller and keeps the system more explainable than a model that predicts raw ETA entirely from scratch.

XGBoost was selected because the main inputs are structured/tabular features. It trains quickly, handles nonlinear relationships well, and supports feature-importance analysis. A sequence model such as LSTM can be evaluated later when sufficient real sequential data is available.

## Dynamic and Explainable ETA

The key feature is continuous recalculation when a new event arrives.

Example:

```text
Initial predicted delay: 3.3 minutes
New delay reported:      +15 minutes
Updated predicted delay: 14.4 minutes
Major contributor:       carried-over delay
```

The system can report the before/after prediction and the major factor responsible for the change instead of simply saying that the ETA increased.

## Uncertainty

Railway ETA is inherently uncertain, so the API is designed to return a predicted delay range rather than presenting a single number as absolute truth.

The current prototype derives its range from prediction-error information on held-out test data. For production, the interval should be recalibrated with real railway outcomes. Conformal prediction or quantile regression can also be evaluated for stronger uncertainty guarantees.

## Model Validation

The development benchmark compares the hybrid model with a simpler baseline.

| Metric | Reported result |
|---|---:|
| Baseline MAE | 4.91 minutes |
| Hybrid Model MAE | 2.03 minutes |
| Improvement | 58.7% |

These figures are **synthetic-benchmark results**, not measured real-world Indian Railways accuracy.

An earlier development benchmark also recorded 4.37 → 1.56 minutes (64%). The final presentation should use only the single benchmark corresponding to the final validated run and should not mix results from different runs.

## Synthetic Data and Bias Limitations

The simulator uses stochastic generation rather than only fixed formulas, and the selected features are based on railway-domain factors. The baseline model also provides a domain-grounded fallback.

However, a train/test split cannot prove generalization from synthetic railway data to real operations. The model may still learn patterns specific to the simulator.

Before production use:

1. Obtain approved real historical/live data.
2. Retrain and revalidate the model.
3. Compare real MAE against the baseline.
4. Check feature importance and prediction direction against domain expectations.
5. Recalibrate uncertainty using real residuals.
6. Run in shadow mode alongside the existing ETA system before operational use.

## Backend

The backend uses FastAPI with Pydantic schemas and a prototype database setup.

### API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/trains` | List trains, routes, and current position |
| GET | `/eta/predict` | Predict ETA at a specific next station |
| GET | `/eta/journey` | Predict ETA at every remaining station |
| POST | `/simulate/delay-event` | Demo-only delay injection and recalculation |

Interactive documentation:

```text
http://localhost:8000/docs
```

Example:

```bash
curl "http://localhost:8000/eta/predict?train_no=12345&current_station_code=NJP&next_station_code=KIR"
```

## Frontend Dashboard

`frontend/RailPulseDashboard.jsx` provides a control-room style live ETA dashboard.

It communicates with the actual FastAPI backend rather than using client-side mock predictions.

The dashboard can show:

- Train selection
- Current route/position
- ETA for remaining stations
- Delay figures
- Delay-contribution chart
- ETA update notification
- Before/after ETA changes

The main demo action is **Simulate live delay event**, which calls the backend, changes the simulated operational state, re-fetches the journey, and displays the updated prediction.

## Project Structure

```text
sih-eta-prediction/
├── data_simulator/
│   └── simulate.py
├── ml/
│   ├── features.py
│   ├── train_model.py
│   └── predict.py
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── routers/
│       └── eta.py
├── frontend/
│   └── RailPulseDashboard.jsx
├── data/
├── models/
└── requirements.txt
```

## Installation

```bash
pip install -r requirements.txt
```

Generate data:

```bash
python data_simulator/simulate.py
```

Train the model:

```bash
python ml/train_model.py
```

Start the API:

```bash
uvicorn backend.main:app --reload
```

Then open:

```text
http://localhost:8000/docs
```

## Technology Stack

- Python
- Pandas
- Scikit-learn
- XGBoost
- Joblib
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite for prototype storage
- React
- Recharts
- Lucide React

## Feasibility and Scalability

RailPulse is software-first and is intended to leverage existing railway data infrastructure rather than require new hardware deployment.

### Proposed rollout

**Phase 1 — Prototype:** synthetic data, ML model, API, dashboard, and end-to-end demo.

**Phase 2 — Pilot:** obtain real data access, retrain, validate, and run in shadow mode on one route/division.

**Phase 3 — Operational deployment:** connect approved feeds, add production security, monitor predictions, and expand.

**Phase 4 — Network scale:** process thousands of trains using distributed streaming, caching, and scalable storage.

For scale, the architecture can evolve toward Kafka for event ingestion, Redis for fast/shared state, PostgreSQL for persistent data, indexed queries, response caching, and dedicated model-serving or batch-scoring infrastructure.

## Operational Use Cases

### Passengers
- More useful forward-looking ETA
- Better planning for boarding and connections
- Clear reasons for ETA changes

### Station Staff
- Earlier arrival visibility
- Better platform planning
- Improved operational coordination

### Control Rooms
- Earlier visibility of cascading delays
- Identification of trains that may create downstream disruption
- Decision support for congested sections

### Accessibility
Future versions can provide ETA through SMS, IVR/voice, and multilingual interfaces.

## Production Security

The current prototype is for development/demo use.

A production deployment should include:

- Restricted CORS
- API authentication and authorization
- Internal protection for simulation/operational endpoints
- Structured logging and request IDs
- Audit logs
- Model/configuration protection
- API latency and failure monitoring

## Monitoring and Retraining

A production feedback loop should compare each prediction with the eventual actual arrival:

```text
Prediction
    ↓
Actual arrival
    ↓
Prediction error
    ↓
MAE / performance monitoring
    ↓
Model evaluation
    ↓
Retraining
```

Performance should be monitored across routes, stations, seasons, weather conditions, and time periods.

## Key Differentiators

- **Existing infrastructure first:** designed to consume existing railway data feeds.
- **Hybrid model:** domain-grounded baseline plus ML correction.
- **Dynamic:** ETA changes as new information arrives.
- **Explainable:** major causes of ETA changes are surfaced.
- **Uncertainty-aware:** provides a delay range rather than false precision.
- **Operational + passenger focused:** supports both public and railway staff use cases.
- **Swap-in ready:** the simulator is separated from the prediction pipeline.

## Demo Flow

```text
Select train
    ↓
Show current ETA
    ↓
Show explanation
    ↓
Trigger simulated live delay
    ↓
Backend recalculates
    ↓
Dashboard refreshes
    ↓
Show before/after ETA
    ↓
Show why it changed
```

The core demonstration message is:

> **RailPulse does not simply display a delay. It dynamically recalculates the future ETA and explains what changed.**

## Known Limitations

- Training and validation currently rely on synthetic data.
- Live Indian Railways GPS/NTES data is not available to the prototype.
- Confidence intervals are not yet calibrated on real railway outcomes.
- The prototype has not been load-tested at full railway scale.
- In-memory state is appropriate for the prototype but not for distributed production.
- Production authentication and security require further implementation.

## Future Enhancements

- Integrate approved real railway GPS/RTIS/operational feeds.
- Retrain and validate using real historical data.
- Evaluate conformal prediction and quantile regression.
- Evaluate LSTM/sequence models for richer journey-level modeling.
- Add a control-room congestion and cascading-delay module.
- Add SMS/IVR and multilingual access.
- Move state to Redis and persistent data to PostgreSQL.
- Introduce Kafka-based real-time ingestion.
- Add automated model monitoring and retraining.
- Perform route-wise and seasonal calibration.
- Conduct production-scale load testing.

## References

The research and implementation were informed by:

1. NTES — National Train Enquiry System.
2. Indian Railways / GPS / RTIS-style real-time tracking concepts.
3. IEEE research on real-time train-delay prediction using machine learning.
4. India-specific research on weather and train delays.
5. XGBoost documentation.
6. FastAPI documentation.

Exact paper titles, authors, publication details, and URLs should be added from the team's final reference list where required.

## Project Status

### Completed

- Synthetic railway data simulator
- Feature engineering pipeline
- XGBoost residual model
- Hybrid ETA prediction
- FastAPI backend
- ETA prediction endpoints
- Dynamic delay-event simulation
- React dashboard integration
- Explainable ETA updates
- End-to-end prototype workflow

### Next Major Milestone

Connect the architecture to an approved real railway dataset/feed and measure real-world performance before making production accuracy claims.

## Conclusion

RailPulse aims to transform railway ETA from a static timetable-based value into a **dynamic, explainable, and uncertainty-aware forecast**.

```text
Railway information
        +
Operational conditions
        +
Historical patterns
        ↓
Hybrid ETA Prediction
        ↓
Dynamic + Explainable + Uncertainty-aware ETA
```

> **Don't just tell passengers that a train is delayed — predict what happens next, explain why, and keep updating the answer as the situation changes.**

---

**RailPulse — Dynamic ETA Forecasting for Indian Railways Coaching Trains**  
**Smart India Hackathon 2026 | Problem Statement 26028 | Team Data Dynamos**
