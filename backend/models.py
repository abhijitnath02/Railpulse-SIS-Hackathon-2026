"""
ORM models. TrainEvent represents one "ping" of a train passing/approaching
a station — this is what a real GPS/NTES feed would push in production, and
what data_simulator/simulate.py mimics for the demo.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime
from .database import Base


class TrainEvent(Base):
    __tablename__ = "train_events"

    id = Column(Integer, primary_key=True, index=True)
    train_no = Column(String, index=True)
    station_code = Column(String, index=True)
    station_seq = Column(Integer)
    distance_km = Column(Float)
    scheduled_time = Column(DateTime)
    actual_time = Column(DateTime)
    delay_minutes = Column(Float)
    weather_factor = Column(Float)
    congestion_factor = Column(Float)
    hour_of_day = Column(Integer)
