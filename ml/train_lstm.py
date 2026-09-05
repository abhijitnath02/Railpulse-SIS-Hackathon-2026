"""
Item 5 — LSTM as a second model for predicting the residual delay,
benchmarked against the existing XGBoost residual model (ml/train_model.py)
on the SAME held-out data.

Why an LSTM here: XGBoost's features (historical_avg_delay,
historical_avg_dwell, delay_so_far, ...) already summarize a journey's
history into single numbers per station. An LSTM instead sees the full
ordered sequence of a train's stations-so-far in one pass, which can in
principle pick up sequential patterns (e.g. "delay has been climbing for
the last 3 stops" vs "delay spiked once and is recovering") that
per-station summary features flatten away.

Leakage control: split is done by WHOLE JOURNEY (train_no, day_id), not by
row. If we split by row, station 5 of a journey could land in train while
station 6 of the SAME journey lands in test, and the model would implicitly
see part of the future it's meant to be predicting. random_state=42 and
the same 80/20 ratio as train_model.py, so the comparison is apples to
apples, but note this is NOT the literal same test set as XGBoost's row-
level split (that one only avoids leakage via feature construction, not
journey-level splitting) — the fairest true comparison is to also refit an
XGBoost split by journey; that's the JOURNEY-SPLIT baseline computed here.

Run: python ml/train_lstm.py
Outputs: models/eta_lstm_model.pt, prints a real MAE + latency comparison
against a journey-split XGBoost model trained inline in this same script
(so the numbers are directly comparable, not pulled from a different run).

REQUIRES: torch (see requirements.txt). This script has NOT been executed
in the assistant's sandbox (no network access to install torch there) —
run it yourself and treat the printed numbers as the source of truth, not
anything claimed in chat before you've run it.
"""
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

from features import build_feature_table, FEATURE_COLUMNS, TARGET_COLUMN

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "train_events.csv"
LSTM_MODEL_PATH = ROOT / "models" / "eta_lstm_model.pt"

SEQ_FEATURE_COLUMNS = FEATURE_COLUMNS  # same 9 features per step, fed as a sequence instead of flattened
HIDDEN_SIZE = 32
NUM_EPOCHS = 25
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def build_journeys(df: pd.DataFrame):
    """Groups rows into one sequence per (train_no, day_id) journey,
    sorted by station_seq — this is the actual physical order a train
    passes through stations, so it's the natural sequence axis for the
    LSTM."""
    journeys = []
    for (train_no, day_id), g in df.groupby(["train_no", "day_id"]):
        g = g.sort_values("station_seq")
        if len(g) < 2:
            continue  # need at least one real step to predict
        journeys.append(g)
    return journeys


def journeys_to_tensors(journeys, feature_means, feature_stds):
    """Pads each journey to the max length in the batch it's used in.
    Returns list of (X_seq [len, n_features] standardized, y_seq [len])
    per journey — kept as a Python list rather than one big padded tensor
    since journey lengths vary a lot across routes (5 to 8 stations)."""
    X_list, y_list = [], []
    for g in journeys:
        X = g[SEQ_FEATURE_COLUMNS].values.astype(np.float32)
        X = (X - feature_means) / feature_stds
        y = g[TARGET_COLUMN].values.astype(np.float32)
        X_list.append(torch.tensor(X))
        y_list.append(torch.tensor(y))
    return X_list, y_list


class ResidualLSTM(nn.Module):
    """Many-to-many: consumes the sequence of per-station feature vectors
    for a journey and predicts the residual delay at EVERY step, so the
    training signal is as dense as the row-level XGBoost model's."""

    def __init__(self, n_features: int, hidden_size: int = HIDDEN_SIZE):
        super().__init__()
        self.lstm = nn.LSTM(input_size=n_features, hidden_size=hidden_size, batch_first=True)
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, x, lengths):
        # x: [batch, max_len, n_features]
        packed = nn.utils.rnn.pack_padded_sequence(x, lengths, batch_first=True, enforce_sorted=False)
        packed_out, _ = self.lstm(packed)
        out, _ = nn.utils.rnn.pad_packed_sequence(packed_out, batch_first=True)
        return self.head(out).squeeze(-1)  # [batch, max_len]


def collate(batch_X, batch_y):
    lengths = [len(x) for x in batch_X]
    max_len = max(lengths)
    n_features = batch_X[0].shape[1]
    X_padded = torch.zeros(len(batch_X), max_len, n_features)
    y_padded = torch.zeros(len(batch_X), max_len)
    mask = torch.zeros(len(batch_X), max_len)
    for i, (x, y) in enumerate(zip(batch_X, batch_y)):
        L = len(x)
        X_padded[i, :L] = x
        y_padded[i, :L] = y
        mask[i, :L] = 1.0
    return X_padded, y_padded, mask, torch.tensor(lengths)


def train_lstm(X_train, y_train, n_features):
    model = ResidualLSTM(n_features).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    loss_fn = nn.L1Loss(reduction="none")  # MAE, matches the eval metric

    n = len(X_train)
    for epoch in range(NUM_EPOCHS):
        perm = np.random.permutation(n)
        total_loss, total_count = 0.0, 0
        for start in range(0, n, BATCH_SIZE):
            idx = perm[start:start + BATCH_SIZE]
            batch_X = [X_train[i] for i in idx]
            batch_y = [y_train[i] for i in idx]
            X_padded, y_padded, mask, lengths = collate(batch_X, batch_y)
            X_padded, y_padded, mask = X_padded.to(DEVICE), y_padded.to(DEVICE), mask.to(DEVICE)

            optimizer.zero_grad()
            preds = model(X_padded, lengths)
            loss_per_elem = loss_fn(preds, y_padded) * mask
            loss = loss_per_elem.sum() / mask.sum()
            loss.backward()
            optimizer.step()

            total_loss += loss_per_elem.sum().item()
            total_count += mask.sum().item()

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  epoch {epoch + 1:>2}/{NUM_EPOCHS}  train MAE: {total_loss / total_count:.3f} min")

    return model


@torch.no_grad()
def evaluate_lstm(model, X_list, y_list):
    """Returns (flat predictions, flat targets, mean per-prediction latency
    in ms) — evaluated one journey at a time, matching how it would be
    called at inference time in eta.py (single train's current state, not
    a giant pre-batched tensor)."""
    model.eval()
    all_preds, all_targets = [], []
    latencies_ms = []
    for X, y in zip(X_list, y_list):
        X_batch = X.unsqueeze(0).to(DEVICE)
        lengths = torch.tensor([len(X)])
        start = time.perf_counter()
        preds = model(X_batch, lengths).squeeze(0).cpu().numpy()
        latencies_ms.append((time.perf_counter() - start) * 1000)
        all_preds.append(preds)
        all_targets.append(y.numpy())
    return np.concatenate(all_preds), np.concatenate(all_targets), float(np.mean(latencies_ms))


def main():
    print("Loading data and building features...")
    raw = pd.read_csv(DATA_PATH, parse_dates=["scheduled_time", "actual_time"])
    df = build_feature_table(raw)

    journeys = build_journeys(df)
    print(f"{len(journeys)} journeys ({df.train_no.nunique()} trains x ~{len(journeys) // max(df.train_no.nunique(), 1)} days)")

    # Journey-level split (leakage-safe) — see module docstring.
    rng = np.random.default_rng(42)
    idx = rng.permutation(len(journeys))
    n_test = int(0.2 * len(journeys))
    test_idx, train_idx = set(idx[:n_test].tolist()), set(idx[n_test:].tolist())
    train_journeys = [journeys[i] for i in sorted(train_idx)]
    test_journeys = [journeys[i] for i in sorted(test_idx)]
    print(f"Journey split: {len(train_journeys)} train journeys, {len(test_journeys)} test journeys")

    # Standardize features using TRAIN stats only (no leakage from test).
    train_concat = pd.concat(train_journeys)
    feature_means = train_concat[SEQ_FEATURE_COLUMNS].values.astype(np.float32).mean(axis=0)
    feature_stds = train_concat[SEQ_FEATURE_COLUMNS].values.astype(np.float32).std(axis=0)
    feature_stds[feature_stds == 0] = 1.0

    X_train, y_train = journeys_to_tensors(train_journeys, feature_means, feature_stds)
    X_test, y_test = journeys_to_tensors(test_journeys, feature_means, feature_stds)

    # --- Train LSTM ---
    print(f"\nTraining LSTM on {DEVICE}...")
    lstm_model = train_lstm(X_train, y_train, n_features=len(SEQ_FEATURE_COLUMNS))

    lstm_preds, lstm_targets, lstm_latency_ms = evaluate_lstm(lstm_model, X_test, y_test)
    lstm_mae = mean_absolute_error(lstm_targets, lstm_preds)

    # --- Train a same-split XGBoost model as the fair comparison point ---
    # (ml/train_model.py's saved model used a ROW-level split, not this
    # journey-level split, so re-fit here rather than reuse that .pkl —
    # otherwise the comparison would be apples-to-oranges on the split.)
    print("\nTraining journey-split XGBoost for a fair comparison...")
    test_concat = pd.concat(test_journeys)
    xgb_model = XGBRegressor(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
    )
    xgb_model.fit(train_concat[FEATURE_COLUMNS], train_concat[TARGET_COLUMN])

    xgb_start = time.perf_counter()
    xgb_preds = xgb_model.predict(test_concat[FEATURE_COLUMNS])
    xgb_total_ms = (time.perf_counter() - xgb_start) * 1000
    xgb_latency_ms = xgb_total_ms / len(test_concat)
    xgb_mae = mean_absolute_error(test_concat[TARGET_COLUMN], xgb_preds)

    print("\n" + "=" * 60)
    print("RESULTS (journey-level held-out test set, no leakage)")
    print("=" * 60)
    print(f"{'Model':<20}{'Test MAE (min)':<18}{'Latency/pred (ms)'}")
    print(f"{'XGBoost (residual)':<20}{xgb_mae:<18.3f}{xgb_latency_ms:.4f}")
    print(f"{'LSTM (residual)':<20}{lstm_mae:<18.3f}{lstm_latency_ms:.4f}")
    print("=" * 60)
    print(
        "NOTE: these numbers come from THIS run, on synthetic data, with "
        "held-out journeys the models never saw during training. They are "
        "not tuned for a specific outcome — rerun this script yourself to "
        "reproduce them."
    )

    LSTM_MODEL_PATH.parent.mkdir(exist_ok=True)
    torch.save({
        "state_dict": lstm_model.state_dict(),
        "feature_means": feature_means,
        "feature_stds": feature_stds,
        "features": SEQ_FEATURE_COLUMNS,
        "hidden_size": HIDDEN_SIZE,
        "test_mae_minutes": float(lstm_mae),
        "xgboost_comparison_mae_minutes": float(xgb_mae),
    }, LSTM_MODEL_PATH)
    print(f"\nSaved LSTM model -> {LSTM_MODEL_PATH}")


if __name__ == "__main__":
    main()
