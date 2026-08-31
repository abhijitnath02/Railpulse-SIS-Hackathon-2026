"""
/trains endpoint — lists the trains available in the demo dataset along
with their route (station list) and current position, so the frontend can
populate a train picker without hardcoding routes on the client side.
"""
from fastapi import APIRouter

from .eta import get_feature_table
from ..schemas import TrainSummary, StationInfo

router = APIRouter(prefix="/trains", tags=["trains"])


@router.get("", response_model=list[TrainSummary])
def list_trains():
    df = get_feature_table()

    summaries = []
    for train_no, group in df.groupby(df.train_no.astype(str)):
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
            stations=stations,
            current_station_code=current_station.code,
            current_station_seq=current_station.station_seq,
        ))

    return summaries
