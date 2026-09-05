"""
/historical endpoints. Wraps ml/predict_historical.py, which serves the
model trained in ml/train_historical_model.py on data/train_delay_data.csv
— a real historical dataset kept deliberately separate from the synthetic
live-operations dataset used everywhere else in this API, so it can be
demoed on its own as "here's the model tested against real historical
records" rather than mixed into the live simulation narrative.
"""
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "ml"))
from predict_historical import predict_historical_delay, get_category_options  # noqa: E402

from .. import models
from ..auth import require_role
from ..schemas import (
    HistoricalPredictionRequest,
    HistoricalPredictionResponse,
    HistoricalFactorContribution,
    HistoricalMetaResponse,
)

router = APIRouter(prefix="/historical", tags=["historical"])


@router.get("/meta", response_model=HistoricalMetaResponse)
def get_historical_meta(_user: models.User = Depends(require_role("viewer"))):
    """Category options + model MAE, read from the trained model bundle so
    the frontend never hardcodes values that could drift from the dataset."""
    try:
        options = get_category_options()
        from predict_historical import _load_bundle
        mae = _load_bundle()["mae"]
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Historical model not trained yet. Run: python ml/train_historical_model.py",
        )

    return HistoricalMetaResponse(
        weather_conditions=options["Weather Conditions"],
        day_of_week=options["Day of the Week"],
        time_of_day=options["Time of Day"],
        train_type=options["Train Type"],
        route_congestion=options["Route Congestion"],
        model_mae_minutes=round(float(mae), 1),
    )


@router.post("/predict", response_model=HistoricalPredictionResponse)
def predict_historical(req: HistoricalPredictionRequest, _user: models.User = Depends(require_role("viewer"))):
    try:
        result = predict_historical_delay({
            "Distance Between Stations (km)": req.distance_km,
            "Weather Conditions": req.weather_conditions,
            "Day of the Week": req.day_of_week,
            "Time of Day": req.time_of_day,
            "Train Type": req.train_type,
            "Route Congestion": req.route_congestion,
        })
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Historical model not trained yet. Run: python ml/train_historical_model.py",
        )

    return HistoricalPredictionResponse(
        predicted_delay_minutes=result.predicted_delay_minutes,
        model_mae_minutes=result.model_mae_minutes,
        factors=[
            HistoricalFactorContribution(feature=f.feature, value=f.value, impact_minutes=f.impact_minutes)
            for f in result.factors
        ],
    )
