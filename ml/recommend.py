"""
Rules-based recommendation layer.

Turns a prediction (delay minutes, contributing factors, congestion) into
short, actionable guidance for control-room/station-staff users — the kind
of "so what do I do about it" output that a bare number doesn't give.

Deliberately rules-based rather than learned: with synthetic data there's
no ground truth for "was this the right operational call", so a model
trained to recommend actions would just be fitting noise. Rules keep this
transparent and easy to justify in a demo, and can be replaced by a
policy/optimization model later once real outcome data exists.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class Recommendation:
    audience: str  # "control_room" | "station_staff" | "passenger"
    priority: str  # "high" | "medium" | "low"
    message: str


def build_recommendations(
    predicted_delay_minutes: float,
    congestion_factor: float,
    cross_train_congestion: int,
    weather_factor: float,
    dwell_extra_minutes: float,
) -> List[Recommendation]:
    recs: List[Recommendation] = []

    # --- Delay severity ---
    if predicted_delay_minutes >= 30:
        recs.append(Recommendation(
            audience="control_room", priority="high",
            message=f"Delay projected at {predicted_delay_minutes:.0f} min — evaluate "
                     f"downstream connections and consider notifying connecting services.",
        ))
        recs.append(Recommendation(
            audience="passenger", priority="high",
            message="Significant delay expected. Check connecting train status before boarding onward services.",
        ))
    elif predicted_delay_minutes >= 15:
        recs.append(Recommendation(
            audience="control_room", priority="medium",
            message=f"Moderate delay ({predicted_delay_minutes:.0f} min) building — monitor "
                     f"for further escalation at the next 1-2 stations.",
        ))
    elif predicted_delay_minutes >= 5:
        recs.append(Recommendation(
            audience="station_staff", priority="low",
            message=f"Minor delay ({predicted_delay_minutes:.0f} min) — no action needed, informational only.",
        ))

    # --- Cross-train congestion ---
    if cross_train_congestion >= 8:
        recs.append(Recommendation(
            audience="control_room", priority="high",
            message=f"{cross_train_congestion} other trains scheduled through this station in "
                     f"the same window — high section congestion risk; consider platform "
                     f"re-sequencing or holding lower-priority movements.",
        ))
    elif cross_train_congestion >= 4:
        recs.append(Recommendation(
            audience="station_staff", priority="medium",
            message=f"{cross_train_congestion} other trains in the same window — plan platform "
                     f"allocation ahead of arrival to avoid dwell overrun.",
        ))

    # --- Weather ---
    if weather_factor >= 1.5:
        recs.append(Recommendation(
            audience="control_room", priority="medium",
            message="Weather conditions are a significant delay contributor — verify speed "
                     "restrictions in effect on this section are reflected in the schedule.",
        ))

    # --- Dwell ---
    if dwell_extra_minutes >= 3:
        recs.append(Recommendation(
            audience="station_staff", priority="medium",
            message=f"Dwell time running {dwell_extra_minutes:.1f} min over normal — check for "
                     f"crew change, loading, or platform-access delays at this stop.",
        ))

    if not recs:
        recs.append(Recommendation(
            audience="passenger", priority="low",
            message="Train is running close to schedule. No action needed.",
        ))

    return recs
