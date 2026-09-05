from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class ETARequest(BaseModel):
    train_no: str
    current_station_code: str
    next_station_code: str


class DeltaContribution(BaseModel):
    """One factor contributing to a change in predicted delay, e.g.
    {"factor": "congestion", "minutes": 3.2}"""
    factor: str
    minutes: float


class ETAChange(BaseModel):
    """Structured explanation of why the ETA moved since the last prediction
    for this train/station, decomposed by contributing factor rather than
    a single vague sentence."""
    previous_predicted_delay_minutes: float
    new_predicted_delay_minutes: float
    change_minutes: float
    contributions: List[DeltaContribution]


class ShapContribution(BaseModel):
    """A single model feature's signed contribution (in minutes) to the
    predicted residual for this specific prediction, from SHAP — distinct
    from `contributions`, which breaks down the *simulated* ground-truth
    delay components rather than what the model itself weighted."""
    feature: str
    value: float
    shap_minutes: float


class Recommendation(BaseModel):
    """One rules-based, audience-tagged action item derived from the
    prediction (delay severity, congestion, weather, dwell overrun)."""
    audience: str  # "control_room" | "station_staff" | "passenger"
    priority: str  # "high" | "medium" | "low"
    message: str


class ETAResponse(BaseModel):
    train_no: str
    next_station_code: str
    scheduled_time: datetime
    predicted_delay_minutes: float
    predicted_eta: datetime
    confidence_lower: datetime
    confidence_upper: datetime
    explanation: str
    contributions: List[DeltaContribution]
    eta_change: Optional[ETAChange] = None
    shap_contributions: List[ShapContribution] = []
    recommendations: List[Recommendation] = []


class StationInfo(BaseModel):
    code: str
    name: str
    distance_km: float
    station_seq: int


class TrainSummary(BaseModel):
    """One entry for the train-list endpoint, used to populate a dropdown
    or sidebar without the client needing to know the route in advance."""
    train_no: str
    route_id: str
    stations: List[StationInfo]
    current_station_code: str
    current_station_seq: int


class AnomalyEvent(BaseModel):
    """One row flagged as a statistical outlier by the Isolation Forest
    anomaly model, e.g. an unusually large delay for that train/station."""
    train_no: str
    route_id: str
    station_code: str
    day_id: int
    delay_minutes: float
    anomaly_score: float


class JourneyStationPrediction(BaseModel):
    """One station's prediction within a full-journey response."""
    station: StationInfo
    scheduled_time: datetime
    predicted_delay_minutes: float
    predicted_eta: datetime
    confidence_lower: datetime
    confidence_upper: datetime
    explanation: str
    contributions: List[DeltaContribution]
    eta_change: Optional[ETAChange] = None
    shap_contributions: List[ShapContribution] = []
    recommendations: List[Recommendation] = []


class JourneyResponse(BaseModel):
    """Full remaining-journey prediction for a train, one entry per
    upcoming station — this is what the dashboard's route view consumes
    in a single call instead of one request per station."""
    train_no: str
    current_station_code: str
    stations: List[JourneyStationPrediction]


class SimulateDelayEventRequest(BaseModel):
    """Simulates a live GPS/NTES update reporting extra delay at a station.
    In production this endpoint would not exist — a real ingestion service
    would write this update — but it lets the demo trigger a believable
    'new data just came in' moment on stage."""
    train_no: str
    station_code: str
    extra_minutes: float


class SimulateDelayEventResponse(BaseModel):
    train_no: str
    station_code: str
    new_delay_minutes: float
    message: str


class HistoricalPredictionRequest(BaseModel):
    """Inputs matching the columns of the uploaded historical dataset
    (data/train_delay_data.csv) — a separate, real dataset used to
    demonstrate the model against actual historical records rather than
    the synthetic live-simulation dataset."""
    distance_km: float
    weather_conditions: str
    day_of_week: str
    time_of_day: str
    train_type: str
    route_congestion: str


class HistoricalFactorContribution(BaseModel):
    feature: str
    value: str
    impact_minutes: float


class HistoricalPredictionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    predicted_delay_minutes: float
    model_mae_minutes: float
    factors: List[HistoricalFactorContribution]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserOut(BaseModel):
    username: str
    role: str
    is_active: bool


class AlertSubscribeRequest(BaseModel):
    train_no: str
    channel: str = "sms"  # "sms" | "push"
    destination: str  # phone number (E.164) or push token
    min_delay_minutes: float = 5.0


class AlertSubscriptionOut(BaseModel):
    id: int
    train_no: str
    channel: str
    destination: str
    min_delay_minutes: float
    is_active: bool


class SentAlertOut(BaseModel):
    """One alert delivery attempt, for demoing/inspecting what would have
    been sent without needing to actually receive an SMS on stage."""
    train_no: str
    channel: str
    destination: str
    message: str
    provider: str  # "twilio" | "stub"
    success: bool
    sent_at: datetime


class HistoricalMetaResponse(BaseModel):
    """Distinct category values the historical model was trained on, so the
    frontend's dropdowns always match the dataset instead of being
    hardcoded on the client."""
    model_config = {"protected_namespaces": ()}

    weather_conditions: List[str]
    day_of_week: List[str]
    time_of_day: List[str]
    train_type: List[str]
    route_congestion: List[str]
    model_mae_minutes: float
