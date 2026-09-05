"""
ORM models. TrainEvent represents one "ping" of a train passing/approaching
a station — this is what a real GPS/NTES feed would push in production, and
what data_simulator/simulate.py mimics for the demo.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from .database import Base


class User(Base):
    """Auth user for RBAC (item 9). Three roles: viewer (read-only),
    operator (can trigger simulated delay events / manage alert
    subscriptions), admin (operator + admin-only endpoints, e.g. user
    management). Demo accounts are seeded on startup — see
    backend/seed.py."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")  # viewer | operator | admin
    is_active = Column(Boolean, default=True)


class AlertSubscription(Base):
    """A passenger/operator subscription to delay alerts for one train
    (item 8). `channel` distinguishes SMS vs push so sms_provider.py and
    a future push provider can both read from the same table."""
    __tablename__ = "alert_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    train_no = Column(String, index=True, nullable=False)
    channel = Column(String, nullable=False, default="sms")  # sms | push
    destination = Column(String, nullable=False)  # phone number or push token
    min_delay_minutes = Column(Float, default=5.0)  # only alert above this threshold
    is_active = Column(Boolean, default=True)


class TrainEvent(Base):
    __tablename__ = "train_events"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(String, index=True)
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
