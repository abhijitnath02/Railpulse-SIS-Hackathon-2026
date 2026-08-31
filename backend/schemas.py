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


class StationInfo(BaseModel):
    code: str
    name: str
    distance_km: float
    station_seq: int


class TrainSummary(BaseModel):
    """One entry for the train-list endpoint, used to populate a dropdown
    or sidebar without the client needing to know the route in advance."""
    train_no: str
    stations: List[StationInfo]
    current_station_code: str
    current_station_seq: int


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
