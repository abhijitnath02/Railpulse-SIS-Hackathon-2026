"""
Cross-train congestion feature.

`congestion_factor` in the raw simulated data is a per-row noise term
attached to a single train's own event — it doesn't capture the fact that
delay at a station is also driven by *other* trains competing for the same
platform/section around the same time. This module adds that signal:

    cross_train_congestion(station, day, hour) =
        number of OTHER trains scheduled at that station on that day
        within a +/- CONGESTION_WINDOW_HOURS window of that hour

This is computed from data available at prediction time (other trains'
*scheduled* times, not their outcomes), so it does not leak the target.
"""
import pandas as pd

CONGESTION_WINDOW_HOURS = 1


def add_cross_train_congestion(df: pd.DataFrame, window_hours: int = CONGESTION_WINDOW_HOURS) -> pd.DataFrame:
    """Adds a `cross_train_congestion` column: count of distinct other
    trains scheduled through the same station on the same day within
    `window_hours` of this row's hour_of_day.

    Grouped by (route_id, station_code, day_id) rather than just
    (station_code, day_id): this project's dataset spans multiple routes
    (see data_simulator/simulate.py), and while none of the current routes
    happen to reuse a station code, real railway station codes can and do
    repeat across zones/divisions. Including route_id in the key keeps this
    correct if a future route ever reuses a code, at no cost today since
    every station code currently maps to exactly one route.
    """
    df = df.copy()

    # Build a lookup of (route_id, station_code, day_id) -> array of
    # (hour_of_day, train_no) for every scheduled event, then count how many
    # *other* trains fall inside the window for each row. Done via groupby
    # + windowed count rather than a full row-by-row scan.
    counts = []
    grouped = df.groupby(["route_id", "station_code", "day_id"])
    lookup = {key: g[["hour_of_day", "train_no"]].values for key, g in grouped}

    for route_id, station_code, day_id, hour_of_day, train_no in df[
        ["route_id", "station_code", "day_id", "hour_of_day", "train_no"]
    ].itertuples(index=False, name=None):
        rows = lookup[(route_id, station_code, day_id)]
        count = 0
        for other_hour, other_train in rows:
            if other_train == train_no:
                continue
            if abs(other_hour - hour_of_day) <= window_hours:
                count += 1
        counts.append(count)

    df["cross_train_congestion"] = counts
    return df
