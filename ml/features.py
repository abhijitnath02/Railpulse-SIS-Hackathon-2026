"""
Feature engineering shared by training (train_model.py) and inference
(predict.py). Keeping this in one place avoids train/serve skew.
"""
import pandas as pd

from congestion import add_cross_train_congestion


FEATURE_COLUMNS = [
    "distance_km",
    "hour_of_day",
    "station_seq",
    "weather_factor",
    "congestion_factor",
    "cross_train_congestion",
    "historical_avg_dwell",
    "historical_avg_delay",
    "delay_so_far",
]

TARGET_COLUMN = "residual_delay"  # actual_delay - simple baseline estimate


def add_historical_avg_delay(df: pd.DataFrame) -> pd.DataFrame:
    """For each (train_no, station_code) pair, compute the historical average
    delay observed at that station, EXCLUDING the current row's own day
    (to avoid leakage) via an expanding-mean-shifted-by-one trick."""
    df = df.sort_values(["train_no", "station_code", "day_id"]).copy()
    grp = df.groupby(["train_no", "station_code"])["delay_minutes"]
    df["historical_avg_delay"] = grp.transform(lambda s: s.shift(1).expanding().mean())
    df["historical_avg_delay"] = df["historical_avg_delay"].fillna(df["delay_minutes"].mean())
    return df


def add_historical_avg_dwell(df: pd.DataFrame) -> pd.DataFrame:
    """Historical average dwell-time overrun at this specific station for this
    train, excluding the current day (same shift-then-expanding-mean trick).
    Dwell is tracked as its own feature since it's a distinct, explainable
    delay source separate from weather/congestion (e.g. crew changes,
    platform congestion at junction stations)."""
    df = df.sort_values(["train_no", "station_code", "day_id"]).copy()
    grp = df.groupby(["train_no", "station_code"])["dwell_extra_minutes"]
    df["historical_avg_dwell"] = grp.transform(lambda s: s.shift(1).expanding().mean())
    df["historical_avg_dwell"] = df["historical_avg_dwell"].fillna(df["dwell_extra_minutes"].mean())
    return df


def add_delay_so_far(df: pd.DataFrame) -> pd.DataFrame:
    """The delay already accumulated at the PREVIOUS station in the same
    journey — the most important real-time signal available at prediction time."""
    df = df.sort_values(["train_no", "day_id", "station_seq"]).copy()
    df["delay_so_far"] = df.groupby(["train_no", "day_id"])["delay_minutes"].shift(1).fillna(0.0)
    return df


def add_baseline_and_residual(df: pd.DataFrame) -> pd.DataFrame:
    """Baseline = naive assumption that delay stays constant from last known
    point (a simple, explainable physics-style baseline). The ML model only
    needs to learn the RESIDUAL on top of this, which is an easier and more
    robust learning problem than predicting delay from scratch."""
    df["baseline_delay"] = df["delay_so_far"]
    df["residual_delay"] = df["delay_minutes"] - df["baseline_delay"]
    return df


def build_feature_table(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df = add_historical_avg_delay(df)
    df = add_historical_avg_dwell(df)
    df = add_delay_so_far(df)
    df = add_cross_train_congestion(df)
    df = add_baseline_and_residual(df)
    return df
