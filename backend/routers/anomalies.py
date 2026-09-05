"""
/anomalies endpoint. Surfaces rows flagged by the Isolation Forest model in
ml/anomaly.py as statistically unusual delay events — a proxy for rare
events. See ml/anomaly.py for the scope caveat: this flags outliers in the
synthetic dataset, it is not validated against real derailments/incidents.
"""
import sys
from pathlib import Path

from fastapi import APIRouter, Depends

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "ml"))
from anomaly import score_anomalies  # noqa: E402

from .eta import get_feature_table
from .. import models
from ..auth import require_role
from ..schemas import AnomalyEvent

router = APIRouter(prefix="/anomalies", tags=["anomalies"])

# scripts/load_test.py exposed this as the single biggest bottleneck in the
# whole API: score_anomalies() runs a 200-tree Isolation Forest's
# decision_function()/predict() over the full feature table, and this was
# being redone on every single request (~5-9s each, and the score doesn't
# even depend on train_no/route_id filters -- those were being applied
# BEFORE scoring, so a differently-filtered request also couldn't reuse
# a previous score). Fix: score the full (unfiltered) table once, cache
# it, and apply train_no/route_id filters to the already-scored result
# afterwards. A threading.Lock prevents concurrent cold-cache requests
# from all recomputing simultaneously (which is what caused this test's
# p95/p99 to be so much worse than the mean).
import threading  # noqa: E402

_scored_cache_key = None
_scored_cache_df = None
_scored_cache_lock = threading.Lock()


def _get_scored(df):
    global _scored_cache_key, _scored_cache_df
    key = (id(df), len(df))
    if _scored_cache_key == key:
        return _scored_cache_df
    with _scored_cache_lock:
        if _scored_cache_key != key:
            _scored_cache_df = score_anomalies(df)
            _scored_cache_key = key
        return _scored_cache_df


@router.get("", response_model=list[AnomalyEvent])
def list_anomalies(
    train_no: str | None = None,
    route_id: str | None = None,
    limit: int = 20,
    _user: models.User = Depends(require_role("viewer")),
):
    """
    Returns the most anomalous recorded delay events, most-anomalous first.
    Optionally filter to a single train or route.

    NOTE: the anomaly score is cached per server process against the
    feature table's identity. /simulate/delay-event mutates a single cell
    of that same table in place, so an injected delay won't be reflected
    here until the process restarts -- acceptable for demo-scale traffic,
    worth re-scoring on a timer or on every /simulate call in production.
    """
    df = get_feature_table()
    scored = _get_scored(df)

    if train_no:
        scored = scored[scored.train_no.astype(str) == str(train_no)]
    if route_id:
        scored = scored[scored.route_id == route_id]

    flagged = scored[scored.is_anomaly].sort_values("anomaly_score", ascending=False).head(limit)

    return [
        AnomalyEvent(
            train_no=str(row["train_no"]),
            route_id=row["route_id"],
            station_code=row["station_code"],
            day_id=int(row["day_id"]),
            delay_minutes=float(row["delay_minutes"]),
            anomaly_score=round(float(row["anomaly_score"]), 4),
        )
        for _, row in flagged.iterrows()
    ]
