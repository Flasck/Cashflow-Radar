"""Forecast Engine core logic: feature engineering, HGB training, and recursive forecasting.

Educational implementation for CashFlow Radar (TSP).
"""

import os

# Limit OpenMP / BLAS threading before numpy/sklearn import
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import datetime
import math
from collections.abc import Callable, Sequence
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

MODEL_VERSION = "hgb-0.1.0"
MIN_HISTORY_DAYS = 30
MAX_HISTORY_DAYS = 1825
ALLOWED_HORIZONS = {7, 30}
INT64_MIN = -9223372036854775808
INT64_MAX = 9223372036854775807


def validate_history_and_horizon(
    history: Sequence[object],
    horizon_days: int,
) -> tuple[list[datetime.date], list[int], list[str]]:
    """Validate history points and horizon strictly according to project spec.

    Returns:
        (dates, minor_values, warnings)
    Raises:
        ValueError if inputs violate constraints (maps to INVALID_ARGUMENT in gRPC).
    """
    if len(history) < MIN_HISTORY_DAYS or len(history) > MAX_HISTORY_DAYS:
        raise ValueError(
            f"History length must be between {MIN_HISTORY_DAYS} and {MAX_HISTORY_DAYS} "
            f"calendar days, got {len(history)}"
        )

    if horizon_days not in ALLOWED_HORIZONS:
        raise ValueError(f"horizon_days must be 7 or 30, got {horizon_days}")

    parsed_dates: list[datetime.date] = []
    minor_values: list[int] = []

    for idx, point in enumerate(history):
        raw_date = getattr(point, "date", None)
        raw_val = getattr(point, "net_cash_flow_minor", None)

        if raw_date is None or raw_val is None:
            raise ValueError(
                f"History point at index {idx} must have 'date' and 'net_cash_flow_minor'"
            )

        raw_str = str(raw_date)
        try:
            d = datetime.date.fromisoformat(raw_str)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid date format at index {idx}: '{raw_date}'. Expected YYYY-MM-DD"
            ) from exc

        if raw_str != d.isoformat():
            raise ValueError(
                f"Invalid date format at index {idx}: '{raw_date}'. Expected strict YYYY-MM-DD"
            )

        try:
            val = int(raw_val)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid net_cash_flow_minor at index {idx}: '{raw_val}'"
            ) from exc

        if val < INT64_MIN or val > INT64_MAX:
            raise ValueError(
                f"net_cash_flow_minor at index {idx} exceeds signed 64-bit integer range: {val}"
            )

        if parsed_dates:
            expected_date = parsed_dates[-1] + datetime.timedelta(days=1)
            if d != expected_date:
                raise ValueError(
                    f"History dates must be strictly consecutive calendar days with step of 1 day: "
                    f"expected {expected_date.isoformat()} after {parsed_dates[-1].isoformat()}, got {d.isoformat()}"
                )

        parsed_dates.append(d)
        minor_values.append(val)

    warnings: list[str] = []
    if len(history) < 90:
        warnings.append("SHORT_HISTORY")

    nonzero_count = sum(1 for v in minor_values if v != 0)
    if nonzero_count < 10:
        warnings.append("SPARSE_HISTORY")

    if len(set(minor_values)) <= 1:
        warnings.append("CONSTANT_HISTORY")

    return parsed_dates, minor_values, warnings


def build_hgb_model() -> HistGradientBoostingRegressor:
    """Create HistGradientBoostingRegressor with exact plan parameters."""
    return HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=100,
        learning_rate=0.05,
        max_depth=3,
        max_leaf_nodes=7,
        min_samples_leaf=3,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=42,
    )


def extract_features_at(
    series: Sequence[float], target_date: datetime.date, t_idx: int
) -> list[float]:
    """Compute features for target day at index t_idx.

    Features:
      lag_1: series[t-1]
      lag_2: series[t-2]
      lag_7: series[t-7]
      mean_7: mean(series[t-7..t-1])
      weekday: 0..6
      day: 1..31
      month: 1..12
    No target leakage: series[t_idx] is NOT used in features.
    """
    if t_idx < 7:
        raise ValueError(f"t_idx must be at least 7 to extract lag 7, got {t_idx}")

    lag_1 = float(series[t_idx - 1])
    lag_2 = float(series[t_idx - 2])
    lag_7 = float(series[t_idx - 7])
    mean_7 = float(np.mean(series[t_idx - 7 : t_idx]))
    weekday = float(target_date.weekday())
    day = float(target_date.day)
    month = float(target_date.month)
    return [lag_1, lag_2, lag_7, mean_7, weekday, day, month]


def build_training_matrix(
    dates: Sequence[datetime.date],
    values_rubles: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    """Construct (X, y) training set for t from index 7 to N-1."""
    n = len(values_rubles)
    if n < 8:
        raise ValueError(f"Need at least 8 points for lagged features, got {n}")

    X_list: list[list[float]] = []
    y_list: list[float] = []

    for t in range(7, n):
        feats = extract_features_at(values_rubles, dates[t], t)
        X_list.append(feats)
        y_list.append(float(values_rubles[t]))

    return np.asarray(X_list, dtype=np.float64), np.asarray(y_list, dtype=np.float64)


def quantize_rubles_to_minor(rubles: float) -> int:
    """Round float rubles to signed int64 kopecks using Decimal ROUND_HALF_UP."""
    if not math.isfinite(rubles):
        raise ValueError(f"Non-finite prediction value: {rubles}")

    dec_rubles = Decimal(str(rubles))
    kopecks_dec = (dec_rubles * Decimal(100)).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    kopecks = int(kopecks_dec)

    if kopecks < INT64_MIN or kopecks > INT64_MAX:
        raise OverflowError(
            f"Quantized kopecks value {kopecks} overflows signed 64-bit integer"
        )

    return kopecks


def run_forecast(
    history_dates: Sequence[datetime.date],
    history_rubles: Sequence[float],
    horizon_days: int,
    is_active_cb: Callable[[], bool] | None = None,
) -> list[tuple[str, int]]:
    """Train HGB on history and perform recursive multi-step forecasting for H days.

    Args:
        history_dates: List of consecutive calendar dates.
        history_rubles: List of float rubles NetCF.
        horizon_days: 7 or 30.
        is_active_cb: Optional callback checking if the RPC call is still active.

    Returns:
        List of (date_iso_string, net_cash_flow_minor_int64) for H days.
    """
    if is_active_cb and not is_active_cb():
        raise RuntimeError("RPC cancelled before feature preparation")

    X_train, y_train = build_training_matrix(history_dates, history_rubles)

    if is_active_cb and not is_active_cb():
        raise RuntimeError("RPC cancelled before fit")

    model = build_hgb_model()
    model.fit(X_train, y_train)

    if is_active_cb and not is_active_cb():
        raise RuntimeError("RPC cancelled after fit")

    # Recursive multi-step forecasting
    simulated_rubles: list[float] = list(history_rubles)
    simulated_dates: list[datetime.date] = list(history_dates)
    forecast_results: list[tuple[str, int]] = []

    for step in range(horizon_days):
        if is_active_cb and not is_active_cb():
            raise RuntimeError(
                f"RPC cancelled during recursive step {step + 1}/{horizon_days}"
            )

        target_date = simulated_dates[-1] + datetime.timedelta(days=1)
        # Features for target_date using current simulated series at index len(simulated_rubles)
        t_idx = len(simulated_rubles)
        feat_vector = extract_features_at(simulated_rubles, target_date, t_idx)

        # Single row prediction
        pred_arr = model.predict(np.asarray([feat_vector], dtype=np.float64))
        pred_val = float(pred_arr[0])

        if not math.isfinite(pred_val):
            raise ValueError(
                f"Model generated non-finite prediction at step {step + 1}: {pred_val}"
            )

        # Append float prediction to simulation for recursive lags
        simulated_rubles.append(pred_val)
        simulated_dates.append(target_date)

        # Output conversion to minor units
        minor_val = quantize_rubles_to_minor(pred_val)
        forecast_results.append((target_date.isoformat(), minor_val))

    return forecast_results


def evaluate_holdout_synthetic(
    total_days: int = 180,
    horizon_days: int = 30,
) -> dict:
    """Educational holdout demonstration on synthetic data comparing HGB and Seasonal Naive.

    Strict chronological split: no random split. Compares MAE and RMSE.
    """
    if horizon_days not in (7, 30):
        raise ValueError("horizon_days must be 7 or 30")
    if total_days <= horizon_days + MIN_HISTORY_DAYS:
        raise ValueError(
            "total_days must be greater than MIN_HISTORY_DAYS + horizon_days"
        )

    # Generate synthetic daily NetCF series: weekly pattern + linear drift + noise
    start_date = datetime.date(2026, 1, 1)
    dates = [start_date + datetime.timedelta(days=i) for i in range(total_days)]

    rng = np.random.RandomState(42)
    # Weekly seasonality: Monday..Sunday
    weekly_pattern = np.array([500.0, 800.0, 750.0, 900.0, 1200.0, -300.0, -400.0])
    y_all: list[float] = []
    for i, d in enumerate(dates):
        w = weekly_pattern[d.weekday()]
        drift = 0.5 * i
        noise = rng.normal(0, 150.0)
        y_all.append(w + drift + noise)

    train_len = total_days - horizon_days
    train_dates = dates[:train_len]
    train_y = y_all[:train_len]
    test_y = y_all[train_len:]

    # Model forecast
    hgb_forecast = run_forecast(train_dates, train_y, horizon_days)
    hgb_preds = [val / 100.0 for _, val in hgb_forecast]

    # Seasonal naive baseline: lag 7 (predicting value from same day of week in previous week)
    seasonal_naive_preds: list[float] = []
    history_extended = list(train_y)
    for step in range(horizon_days):
        # Value from 7 days ago
        pred = history_extended[-7]
        seasonal_naive_preds.append(pred)
        history_extended.append(pred)

    actuals = np.array(test_y, dtype=np.float64)
    hgb_arr = np.array(hgb_preds, dtype=np.float64)
    snaive_arr = np.array(seasonal_naive_preds, dtype=np.float64)

    hgb_mae = float(np.mean(np.abs(actuals - hgb_arr)))
    hgb_rmse = float(np.sqrt(np.mean((actuals - hgb_arr) ** 2)))

    snaive_mae = float(np.mean(np.abs(actuals - snaive_arr)))
    snaive_rmse = float(np.sqrt(np.mean((actuals - snaive_arr) ** 2)))

    return {
        "train_days": train_len,
        "horizon_days": horizon_days,
        "hgb": {"mae_rubles": hgb_mae, "rmse_rubles": hgb_rmse},
        "seasonal_naive": {"mae_rubles": snaive_mae, "rmse_rubles": snaive_rmse},
    }
