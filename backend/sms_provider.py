"""
SMS/push alert delivery (item 8), with two paths:

  1. Real Twilio path — auto-activates if TWILIO_ACCOUNT_SID,
     TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER are all set in the
     environment. Requires `pip install twilio` (not in requirements.txt
     by default, since most demo environments won't have a Twilio
     account — add it yourself if you do).
  2. Stub path — always available, zero external dependency. Instead of
     actually sending anything, it formats the message exactly as it
     would be sent, logs it, and records it in an in-memory list that
     /alerts/sent exposes — so the demo can show "here's the SMS that
     would have gone out" without needing a funded SMS account on stage.

This is a genuine gap from a production system: the stub proves the
integration point and message formatting work, but does not prove SMS
actually arrives on a real handset, which needs a funded Twilio (or
equivalent) account and phone number.
"""
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List


@dataclass
class SentAlert:
    train_no: str
    channel: str
    destination: str
    message: str
    provider: str
    success: bool
    sent_at: datetime


# In-memory log of everything "sent" this process — demo/debug only, not
# persisted, mirrors the pattern already used for _last_prediction_cache
# in eta.py for a single-instance demo.
_sent_log: List[SentAlert] = []


def get_sent_log() -> List[SentAlert]:
    return list(reversed(_sent_log))  # most recent first


class StubSmsProvider:
    """Formats and logs the message it would send; never makes a network
    call. Always 'succeeds' so the alert pipeline is fully demoable."""

    name = "stub"

    def send(self, destination: str, message: str) -> bool:
        print(f"[sms-stub] -> {destination}: {message}")
        return True


class TwilioSmsProvider:
    """Real delivery via Twilio. Only constructed if credentials are
    present (see get_sms_provider() below); import of the twilio package
    is deferred to construction time so the stub path never needs it
    installed."""

    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        from twilio.rest import Client  # deferred import — optional dependency

        self._client = Client(account_sid, auth_token)
        self._from_number = from_number

    def send(self, destination: str, message: str) -> bool:
        try:
            self._client.messages.create(body=message, from_=self._from_number, to=destination)
            return True
        except Exception as exc:  # noqa: BLE001 — surface any Twilio error as a failed send
            print(f"[sms-twilio] send failed for {destination}: {exc}")
            return False


def get_sms_provider():
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    if sid and token and from_number:
        try:
            return TwilioSmsProvider(sid, token, from_number)
        except ImportError:
            print("[sms] TWILIO_* env vars set but `twilio` package not installed — falling back to stub.")
    return StubSmsProvider()


def format_delay_alert(train_no: str, station_code: str, new_delay_minutes: float) -> str:
    return (
        f"RailPulse alert: Train {train_no} is now running "
        f"{new_delay_minutes:.0f} min late approaching {station_code}."
    )


def send_alert(destination: str, channel: str, train_no: str, message: str) -> SentAlert:
    """channel is currently always routed to the SMS provider — push would
    plug in as a second provider behind the same interface (send(dest,
    message) -> bool) and be selected here by `channel`."""
    provider = get_sms_provider()
    success = provider.send(destination, message)
    record = SentAlert(
        train_no=train_no,
        channel=channel,
        destination=destination,
        message=message,
        provider=provider.name,
        success=success,
        sent_at=datetime.now(timezone.utc),
    )
    _sent_log.append(record)
    return record
