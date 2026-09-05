"""
/eta endpoints. For the demo, current train state (delay so far, historical
average delay/dwell at a station) is looked up from the simulated dataset
rather than a live GPS feed — in production this would come from the
TrainEvent table populated by a real-time ingestion service (see
backend/models.py).

Two things this router is specifically built to demonstrate for the
"dynamic forecast" requirement of PS 26028:
  1. Every call recalculates the ETA from the latest known state.
  2. The response explains *why* the delay is what it is using the actual
     simulated delay components (weather / congestion / dwell / random
     events), and if a previous prediction exists for this train+station in
     this server session, it reports a structured breakdown of what changed.

/eta/journey wraps the single-station logic to return the full remaining
route in one call, which is what the frontend route view consumes.
"""
import sys
from pathlib import Path
from datetime import timedelta

import pandas as pd
from fastapi import APIRouter, HTTPException, Depends

from .. import models
from ..auth import require_role
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "ml"))
from predict import predict_delay  # noqa: E402
from features import build_feature_table  # noqa: E402
from recommend import build_recommendations  # noqa: E402

from ..schemas import (
    ETAResponse,
    ETAChange,
    DeltaContribution,
    JourneyResponse,
    JourneyStationPrediction,
    StationInfo,
    ShapContribution,
    Recommendation,
)

router = APIRouter(prefix="/eta", tags=["eta"])

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "train_events.csv"
_cached_df = None

# In-memory "last prediction" cache keyed by "train_no|station_code".
# In production this would be a Redis entry per train/station rather than a
# process-local dict, but for a single-instance demo this is sufficient to
# show the "ETA changed because X" behaviour across successive calls.
_last_prediction_cache: dict = {}


def get_feature_table(force_reload: bool = False) -> pd.DataFrame:
    """Exposed (not underscore-prefixed) so other routers, e.g. the delay-
    event simulator, can mutate the same in-memory table."""
    global _cached_df
    if _cached_df is None or force_reload:
        raw = pd.read_csv(DATA_PATH, parse_dates=["scheduled_time", "actual_time"])
        _cached_df = build_feature_table(raw)
    return _cached_df


def _build_contributions(row: pd.Series, delay_so_far: float) -> list:
    """Break the predicted delay down into the real simulated components,
    so the explanation is grounded in actual causes rather than guesswork."""
    return [
        DeltaContribution(factor="carried_over_delay", minutes=round(float(delay_so_far), 1)),
        DeltaContribution(factor="weather", minutes=round(float(row["weather_delay_contrib"]), 1)),
        DeltaContribution(factor="congestion", minutes=round(float(row["congestion_delay_contrib"]), 1)),
        DeltaContribution(factor="station_dwell", minutes=round(float(row["dwell_extra_minutes"]), 1)),
        DeltaContribution(factor="unscheduled_events", minutes=round(float(row["random_event_delay_contrib"]), 1)),
    ]


def _predict_one_station(df: pd.DataFrame, train_no: str, current_station_code: str, next_station_code: str) -> dict:
    """Core prediction logic shared by /predict and /journey. Returns a
    plain dict rather than a pydantic model so callers can adapt the shape
    (ETAResponse vs JourneyStationPrediction) without re-computing."""
    train_no_str = str(train_no)
    df_train_no_str = df.train_no.astype(str)

    current_rows = df[(df_train_no_str == train_no_str) & (df.station_code == current_station_code)]
    next_rows = df[(df_train_no_str == train_no_str) & (df.station_code == next_station_code)]

    if current_rows.empty or next_rows.empty:
        raise HTTPException(status_code=404, detail="Train or station not found in dataset")

    current = current_rows.sort_values("day_id").iloc[-1]
    next_station = next_rows.sort_values("day_id").iloc[-1]

    feature_row = {
        "distance_km": next_station["distance_km"],
        "hour_of_day": next_station["hour_of_day"],
        "station_seq": next_station["station_seq"],
        "weather_factor": next_station["weather_factor"],
        "congestion_factor": next_station["congestion_factor"],
        "cross_train_congestion": next_station["cross_train_congestion"],
        "historical_avg_dwell": next_station["historical_avg_dwell"],
        "historical_avg_delay": next_station["historical_avg_delay"],
        "delay_so_far": current["delay_minutes"],
    }

    result = predict_delay(feature_row)

    shap_contributions = [
        ShapContribution(feature=c.feature, value=c.value, shap_minutes=c.shap_minutes)
        for c in result.shap_contributions
    ]

    recommendations = [
        Recommendation(audience=r.audience, priority=r.priority, message=r.message)
        for r in build_recommendations(
            predicted_delay_minutes=result.predicted_delay_minutes,
            congestion_factor=float(next_station["congestion_factor"]),
            cross_train_congestion=int(next_station["cross_train_congestion"]),
            weather_factor=float(next_station["weather_factor"]),
            dwell_extra_minutes=float(next_station["dwell_extra_minutes"]),
        )
    ]

    scheduled_time = next_station["scheduled_time"]
    predicted_eta = scheduled_time + timedelta(minutes=result.predicted_delay_minutes)
    confidence_lower = scheduled_time + timedelta(minutes=result.lower_bound_minutes)
    confidence_upper = scheduled_time + timedelta(minutes=result.upper_bound_minutes)

    contributions = _build_contributions(next_station, feature_row["delay_so_far"])
    top_factor = max(contributions, key=lambda c: c.minutes)
    explanation = (
        f"Largest contributor: {top_factor.factor.replace('_', ' ')} "
        f"(+{top_factor.minutes:.1f} min)" if top_factor.minutes > 1
        else "running close to schedule"
    )

    cache_key = f"{train_no_str}|{next_station_code}"
    eta_change = None
    previous = _last_prediction_cache.get(cache_key)
    if previous is not None:
        factor_deltas = []
        prev_contribs = {c["factor"]: c["minutes"] for c in previous["contributions"]}
        for c in contributions:
            prev_val = prev_contribs.get(c.factor, 0.0)
            diff = round(c.minutes - prev_val, 1)
            if abs(diff) >= 0.1:
                factor_deltas.append(DeltaContribution(factor=c.factor, minutes=diff))

        if abs(round(result.predicted_delay_minutes - previous["predicted_delay_minutes"], 1)) >= 0.1:
            eta_change = ETAChange(
                previous_predicted_delay_minutes=previous["predicted_delay_minutes"],
                new_predicted_delay_minutes=result.predicted_delay_minutes,
                change_minutes=round(result.predicted_delay_minutes - previous["predicted_delay_minutes"], 1),
                contributions=factor_deltas,
            )

    _last_prediction_cache[cache_key] = {
        "predicted_delay_minutes": result.predicted_delay_minutes,
        "contributions": [{"factor": c.factor, "minutes": c.minutes} for c in contributions],
    }

    return {
        "station": StationInfo(
            code=next_station["station_code"],
            name=next_station["station_name"],
            distance_km=float(next_station["distance_km"]),
            station_seq=int(next_station["station_seq"]),
        ),
        "scheduled_time": scheduled_time,
        "predicted_delay_minutes": result.predicted_delay_minutes,
        "predicted_eta": predicted_eta,
        "confidence_lower": confidence_lower,
        "confidence_upper": confidence_upper,
        "explanation": explanation,
        "contributions": contributions,
        "eta_change": eta_change,
        "shap_contributions": shap_contributions,
        "recommendations": recommendations,
    }


@router.get("/predict", response_model=ETAResponse)
def get_eta_prediction(
    train_no: str,
    current_station_code: str,
    next_station_code: str,
    _user: models.User = Depends(require_role("viewer")),
):
    """
    Predicts the ETA at `next_station_code` for `train_no`, given it has
    just been observed at `current_station_code`. Call this again later
    with fresher "current" state to see the ETA dynamically update.
    """
    df = get_feature_table()
    r = _predict_one_station(df, train_no, current_station_code, next_station_code)
    return ETAResponse(
        train_no=train_no,
        next_station_code=r["station"].code,
        scheduled_time=r["scheduled_time"],
        predicted_delay_minutes=r["predicted_delay_minutes"],
        predicted_eta=r["predicted_eta"],
        confidence_lower=r["confidence_lower"],
        confidence_upper=r["confidence_upper"],
        explanation=r["explanation"],
        contributions=r["contributions"],
        eta_change=r["eta_change"],
        shap_contributions=r["shap_contributions"],
        recommendations=r["recommendations"],
    )


@router.get("/journey", response_model=JourneyResponse)
def get_full_journey(
    train_no: str,
    current_station_code: str,
    _user: models.User = Depends(require_role("viewer")),
):
    """
    Predicts the ETA at every remaining station for `train_no`, given it
    has just been observed at `current_station_code`. This is what the
    dashboard's route view calls, instead of one request per station.
    """
    df = get_feature_table()
    train_no_str = str(train_no)
    df_train_no_str = df.train_no.astype(str)

    train_rows = df[df_train_no_str == train_no_str].sort_values("station_seq")
    if train_rows.empty:
        raise HTTPException(status_code=404, detail="Train not found in dataset")

    current_rows = train_rows[train_rows.station_code == current_station_code]
    if current_rows.empty:
        raise HTTPException(status_code=404, detail="Current station not found on this train's route")

    current_seq = int(current_rows.iloc[0]["station_seq"])
    remaining = train_rows[train_rows.station_seq > current_seq].drop_duplicates("station_code")

    station_predictions = []
    for _, row in remaining.iterrows():
        r = _predict_one_station(df, train_no, current_station_code, row["station_code"])
        station_predictions.append(JourneyStationPrediction(
            station=r["station"],
            scheduled_time=r["scheduled_time"],
            predicted_delay_minutes=r["predicted_delay_minutes"],
            predicted_eta=r["predicted_eta"],
            confidence_lower=r["confidence_lower"],
            confidence_upper=r["confidence_upper"],
            explanation=r["explanation"],
            contributions=r["contributions"],
            eta_change=r["eta_change"],
            shap_contributions=r["shap_contributions"],
            recommendations=r["recommendations"],
        ))

    return JourneyResponse(
        train_no=train_no,
        current_station_code=current_station_code,
        stations=station_predictions,
    )
