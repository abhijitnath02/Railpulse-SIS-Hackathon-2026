"""
/trains endpoint — lists the trains available in the demo dataset along
with their route (station list) and current position, so the frontend can
populate a train picker without hardcoding routes on the client side.
"""
from fastapi import APIRouter, Depends
import threading

from .eta import get_feature_table
from .. import models
from ..auth import require_role
from ..schemas import TrainSummary, StationInfo

router = APIRouter(prefix="/trains", tags=["trains"])

# scripts/load_test.py exposed this as a real bottleneck: building the
# summary list involves a groupby + per-route iterrows() over the full
# feature table, which was being redone from scratch on every single
# request (p95 latency reached 13s under 20-way concurrent load). The
# underlying data doesn't change between calls except via
# /simulate/delay-event (which mutates the SAME cached dataframe object
# in place -- see eta.py's get_feature_table), so caching the built
# summaries here, keyed on that dataframe's identity, is safe and cuts
# this to one build per server process.
_summary_cache_key = None
_summary_cache: list[TrainSummary] | None = None
_summary_cache_lock = threading.Lock()


def _build_summaries(df) -> list[TrainSummary]:
    summaries = []
    for (route_id, train_no), group in df.groupby([df.route_id, df.train_no.astype(str)]):
        route = group.sort_values("station_seq").drop_duplicates("station_code")
        stations = [
            StationInfo(
                code=row["station_code"],
                name=row["station_name"],
                distance_km=float(row["distance_km"]),
                station_seq=int(row["station_seq"]),
            )
            for _, row in route.iterrows()
        ]

        # For the demo, treat the train as "currently at" a middling station
        # along its route rather than always station 0, so the route view
        # has some completed stations and some upcoming ones to show.
        mid_idx = max(0, len(stations) // 3)
        current_station = stations[mid_idx]

        summaries.append(TrainSummary(
            train_no=train_no,
            route_id=route_id,
            stations=stations,
            current_station_code=current_station.code,
            current_station_seq=current_station.station_seq,
        ))
    return summaries


def get_cached_summaries(df) -> list[TrainSummary]:
    global _summary_cache_key, _summary_cache
    key = (id(df), len(df))
    if _summary_cache_key == key and _summary_cache is not None:
        return _summary_cache
    # Same lock-guarded pattern as anomalies.py's _get_scored: without it,
    # concurrent requests all miss a cold cache at once and all pay the
    # full groupby+iterrows cost simultaneously, which is exactly what
    # caused /trains' p95/p99 latency to stay at ~12s even after adding
    # the cache (only the *repeat* p50 got fast).
    with _summary_cache_lock:
        if _summary_cache_key != key or _summary_cache is None:
            _summary_cache = _build_summaries(df)
            _summary_cache_key = key
        return _summary_cache


@router.get("", response_model=list[TrainSummary])
def list_trains(_user: models.User = Depends(require_role("viewer"))):
    df = get_feature_table()
    return get_cached_summaries(df)
