"""
/alerts endpoints (item 8 — SMS/push alerts for low-connectivity riders).

Design: a passenger (or operator, on a passenger's behalf) subscribes a
phone number/push token to a specific train. When a delay event is
recorded for that train (see simulate.py's call into notify_subscribers
below), every active subscription for that train whose
min_delay_minutes threshold is crossed gets a message via
backend/sms_provider.py.

Subscribing itself needs no special role (any authenticated user, since a
passenger subscribing to their own train is exactly what viewer accounts
are for). Triggering a notification manually and reading the raw sent-log
are operator/admin actions since they're operational tooling, not
passenger-facing.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import get_current_user, require_role
from ..schemas import AlertSubscribeRequest, AlertSubscriptionOut, SentAlertOut
from ..sms_provider import send_alert, format_delay_alert, get_sent_log

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/subscribe", response_model=AlertSubscriptionOut)
def subscribe(
    payload: AlertSubscribeRequest,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    if payload.channel not in ("sms", "push"):
        raise HTTPException(status_code=400, detail="channel must be 'sms' or 'push'")

    sub = models.AlertSubscription(
        train_no=payload.train_no,
        channel=payload.channel,
        destination=payload.destination,
        min_delay_minutes=payload.min_delay_minutes,
        is_active=True,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return AlertSubscriptionOut(
        id=sub.id, train_no=sub.train_no, channel=sub.channel,
        destination=sub.destination, min_delay_minutes=sub.min_delay_minutes,
        is_active=sub.is_active,
    )


@router.delete("/unsubscribe/{subscription_id}")
def unsubscribe(
    subscription_id: int,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    sub = db.query(models.AlertSubscription).filter(models.AlertSubscription.id == subscription_id).first()
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.is_active = False
    db.commit()
    return {"id": subscription_id, "is_active": False}


@router.get("/subscriptions", response_model=List[AlertSubscriptionOut])
def list_subscriptions(
    train_no: str | None = None,
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_role("operator")),
):
    q = db.query(models.AlertSubscription).filter(models.AlertSubscription.is_active.is_(True))
    if train_no:
        q = q.filter(models.AlertSubscription.train_no == train_no)
    return [
        AlertSubscriptionOut(
            id=s.id, train_no=s.train_no, channel=s.channel, destination=s.destination,
            min_delay_minutes=s.min_delay_minutes, is_active=s.is_active,
        )
        for s in q.all()
    ]


@router.get("/sent", response_model=List[SentAlertOut])
def list_sent_alerts(_user: models.User = Depends(require_role("operator"))):
    """Demo/debug endpoint: what would have gone out, in order, most
    recent first. Real value is proving the pipeline fired, not the
    actual SMS delivery (see sms_provider.py's stub-vs-Twilio note)."""
    return [
        SentAlertOut(
            train_no=a.train_no, channel=a.channel, destination=a.destination,
            message=a.message, provider=a.provider, success=a.success, sent_at=a.sent_at,
        )
        for a in get_sent_log()
    ]


def notify_subscribers(db: Session, train_no: str, station_code: str, new_delay_minutes: float) -> int:
    """Called from simulate.py after a delay event is recorded. Returns
    the number of alerts sent. Not exposed as its own endpoint — it's
    triggered as a side effect of a real delay event, matching how a
    production ingestion pipeline would fire alerts off a Kafka consumer
    rather than a separate manual API call."""
    subs = (
        db.query(models.AlertSubscription)
        .filter(models.AlertSubscription.train_no == train_no)
        .filter(models.AlertSubscription.is_active.is_(True))
        .filter(models.AlertSubscription.min_delay_minutes <= new_delay_minutes)
        .all()
    )
    message = format_delay_alert(train_no, station_code, new_delay_minutes)
    sent_count = 0
    for sub in subs:
        result = send_alert(sub.destination, sub.channel, train_no, message)
        if result.success:
            sent_count += 1
    return sent_count
