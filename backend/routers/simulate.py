"""
/simulate endpoints. This router exists ONLY for the demo: in production,
delay updates would arrive from a real ingestion service (Kafka consumer
writing to the TrainEvent table, see backend/models.py), not from a client
calling an API to inject fake data.

For the demo, this lets the "simulate live delay event" button on the
dashboard cause a REAL change in backend state, which then flows through
the actual prediction pipeline (features -> model -> API response) rather
than being faked entirely on the client. Subsequent calls to /eta/predict
or /eta/journey for the same train will reflect this update and produce a
genuine eta_change block, backed by the real model.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .eta import get_feature_table
from .alerts import notify_subscribers
from ..auth import require_role
from ..database import get_db
from .. import models
from ..schemas import SimulateDelayEventRequest, SimulateDelayEventResponse

router = APIRouter(prefix="/simulate", tags=["simulate"])


@router.post("/delay-event", response_model=SimulateDelayEventResponse)
def simulate_delay_event(
    payload: SimulateDelayEventRequest,
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_role("operator")),
):
    """
    Adds `extra_minutes` of delay to the most recent recorded row for
    `train_no` at `station_code`, mimicking a live GPS/NTES update
    reporting the train is more delayed than previously known.

    Requires operator or admin role (item 9) — this mutates shared demo
    state, so a viewer account cannot trigger it. On success, also fans
    out delay alerts (item 8) to any active subscribers for this train
    whose threshold is crossed.
    """
    df = get_feature_table()
    train_no_str = str(payload.train_no)
    mask = (df.train_no.astype(str) == train_no_str) & (df.station_code == payload.station_code)

    if not mask.any():
        raise HTTPException(status_code=404, detail="Train or station not found in dataset")

    # Mutate the most recent day's row for this train/station — this is the
    # row _predict_one_station() treats as the "live" current state.
    idx = df[mask].sort_values("day_id").index[-1]
    df.loc[idx, "delay_minutes"] = df.loc[idx, "delay_minutes"] + payload.extra_minutes
    new_delay = float(df.loc[idx, "delay_minutes"])

    alerts_sent = notify_subscribers(
        db, train_no=payload.train_no, station_code=payload.station_code, new_delay_minutes=new_delay,
    )

    return SimulateDelayEventResponse(
        train_no=payload.train_no,
        station_code=payload.station_code,
        new_delay_minutes=new_delay,
        message=(
            f"Recorded +{payload.extra_minutes:.1f} min delay at {payload.station_code} "
            f"for train {payload.train_no} ({alerts_sent} alert(s) sent)"
        ),
    )
