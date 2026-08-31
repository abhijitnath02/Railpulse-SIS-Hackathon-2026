"""
Synthetic data generator for train journeys.

Generates a realistic dataset of train journey "events" — a train passing
a station at a point in time, with a schedule and an actual delay that
depends on congestion, weather, and time-of-day, similar to how a real
NTES/GPS feed would look. Output: data/train_events.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)

# A handful of stations along a sample route (NJP -> Guwahati corridor style)
STATIONS = [
    ("NJP", "New Jalpaiguri", 0),
    ("KIR", "Kishanganj", 55),
    ("BOE", "Barsoi", 110),
    ("KNE", "Katihar", 150),
    ("MLDT", "Malda Town", 220),
    ("NFK", "New Farakka", 260),
    ("SGUJ", "Sahibganj", 320),
    ("BJU", "Barauni", 420),
]

NUM_TRAINS = 30
NUM_DAYS = 120  # simulate ~4 months of daily runs per train


def weather_factor(day_of_year: int) -> float:
    """Winter months (Dec-Feb) get foggy in this corridor -> higher delay factor."""
    month = pd.Timestamp("2025-01-01") + pd.Timedelta(days=day_of_year % 365)
    if month.month in (12, 1, 2):
        return RNG.normal(1.4, 0.2)
    if month.month in (6, 7, 8):  # monsoon
        return RNG.normal(1.2, 0.15)
    return RNG.normal(1.0, 0.1)


def congestion_factor(hour: int) -> float:
    """Peak hours have more traffic on the line -> more signal halts."""
    if hour in (7, 8, 9, 18, 19, 20):
        return RNG.normal(1.3, 0.1)
    return RNG.normal(1.0, 0.08)


def dwell_extra_minutes(station_seq: int, num_stations: int) -> float:
    """Extra time spent stopped at a station beyond its scheduled halt —
    e.g. extra loading time, platform congestion, crew changes. Junction-like
    stations (roughly every 3rd stop) tend to run longer halts."""
    is_junction_like = (station_seq % 3 == 0) and (0 < station_seq < num_stations - 1)
    base = RNG.exponential(scale=2.5 if is_junction_like else 1.0)
    return max(0.0, base)


def simulate_train(train_no: str, base_speed_kmph: float):
    rows = []
    for day in range(NUM_DAYS):
        dep_hour = RNG.integers(4, 22)
        base_time = pd.Timestamp("2025-01-01") + pd.Timedelta(days=day, hours=int(dep_hour))
        cumulative_delay = 0.0

        for i, (code, name, dist_km) in enumerate(STATIONS):
            sched_time = base_time + pd.Timedelta(hours=dist_km / base_speed_kmph)

            wf = max(weather_factor(day), 0.7)
            cf = max(congestion_factor(sched_time.hour), 0.7)
            dwell_extra = dwell_extra_minutes(i, len(STATIONS))

            # random operational delay events: signal halt, unscheduled stop, etc.
            random_event_delay = RNG.exponential(scale=4.0) if RNG.random() < 0.25 else 0.0

            weather_delay = (wf - 1) * 15
            congestion_delay = (cf - 1) * 20
            segment_extra_delay = weather_delay + congestion_delay + dwell_extra + random_event_delay
            cumulative_delay = max(0.0, cumulative_delay * 0.7 + segment_extra_delay)

            actual_time = sched_time + pd.Timedelta(minutes=cumulative_delay)

            rows.append({
                "train_no": train_no,
                "day_id": day,
                "station_code": code,
                "station_name": name,
                "distance_km": dist_km,
                "scheduled_time": sched_time,
                "actual_time": actual_time,
                "delay_minutes": round(cumulative_delay, 1),
                "weather_factor": round(wf, 2),
                "congestion_factor": round(cf, 2),
                "dwell_extra_minutes": round(dwell_extra, 2),
                "weather_delay_contrib": round(weather_delay, 2),
                "congestion_delay_contrib": round(congestion_delay, 2),
                "random_event_delay_contrib": round(random_event_delay, 2),
                "hour_of_day": sched_time.hour,
                "station_seq": i,
            })
    return rows


def main():
    all_rows = []
    for t in range(NUM_TRAINS):
        train_no = f"1{2000 + t}"
        base_speed = RNG.uniform(45, 75)  # kmph, varies by train type
        all_rows.extend(simulate_train(train_no, base_speed))

    df = pd.DataFrame(all_rows)
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "train_events.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} rows for {NUM_TRAINS} trains -> {out_path}")


if __name__ == "__main__":
    main()
