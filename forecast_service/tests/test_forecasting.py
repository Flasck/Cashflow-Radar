import datetime
from types import SimpleNamespace

import pytest

from forecast_service.forecasting import (
    build_training_matrix,
    evaluate_holdout_synthetic,
    quantize_rubles_to_minor,
    run_forecast,
    validate_history_and_horizon,
)


def make_history(
    n_days: int, start_date: datetime.date = datetime.date(2026, 1, 1), value_fn=None
):
    if value_fn is None:
        value_fn = lambda i: 100_000 + (i % 7) * 10_000
    points = []
    for i in range(n_days):
        d = start_date + datetime.timedelta(days=i)
        points.append(
            SimpleNamespace(date=d.isoformat(), net_cash_flow_minor=value_fn(i))
        )
    return points


def test_29_days_rejected():
    history = make_history(29)
    with pytest.raises(ValueError, match="History length must be between 30 and 1825"):
        validate_history_and_horizon(history, 7)


def test_30_days_accepted():
    history = make_history(30)
    dates, vals, warnings = validate_history_and_horizon(history, 7)
    assert len(dates) == 30
    assert len(vals) == 30
    assert "SHORT_HISTORY" in warnings


def test_over_1825_days_rejected():
    history = make_history(1826)
    with pytest.raises(ValueError, match="History length must be between 30 and 1825"):
        validate_history_and_horizon(history, 7)


def test_horizon_validation():
    history = make_history(30)
    # 7 and 30 are valid
    validate_history_and_horizon(history, 7)
    validate_history_and_horizon(history, 30)

    for invalid_h in [0, 1, 14, 28, 31, 60]:
        with pytest.raises(ValueError, match="horizon_days must be 7 or 30"):
            validate_history_and_horizon(history, invalid_h)


def test_date_holes_and_duplicates_rejected():
    # Gap of 1 day
    p1 = [
        SimpleNamespace(date=f"2026-01-{i:02d}", net_cash_flow_minor=100)
        for i in range(1, 15)
    ]
    p2 = [
        SimpleNamespace(date=f"2026-01-{i:02d}", net_cash_flow_minor=100)
        for i in range(16, 32)
    ]
    gap_history = p1 + p2
    with pytest.raises(ValueError, match="strictly consecutive calendar days"):
        validate_history_and_horizon(gap_history, 7)

    # Duplicate day
    dup_history = make_history(30)
    dup_history[10].date = dup_history[9].date
    with pytest.raises(ValueError, match="strictly consecutive calendar days"):
        validate_history_and_horizon(dup_history, 7)


def test_invalid_date_format_rejected():
    history = make_history(30)
    history[5].date = "not-a-date"
    with pytest.raises(ValueError, match="Invalid date format"):
        validate_history_and_horizon(history, 7)

    # Basic format like YYYYMMDD accepted by fromisoformat in Python 3.11+, but rejected by strict ISO YYYY-MM-DD
    history[5].date = "20260106"
    with pytest.raises(ValueError, match="Expected strict YYYY-MM-DD"):
        validate_history_and_horizon(history, 7)


def test_warnings_short_sparse_constant():
    # Constant zeros: length 30 (<90), 0 non-zero (<10), constant
    zeros = make_history(30, value_fn=lambda _: 0)
    _, _, warnings = validate_history_and_horizon(zeros, 30)
    assert "SHORT_HISTORY" in warnings
    assert "SPARSE_HISTORY" in warnings
    assert "CONSTANT_HISTORY" in warnings

    # Constant non-zero 100 days: >=90 (not short), 100 non-zero (not sparse), constant
    const_non_zero = make_history(100, value_fn=lambda _: 50000)
    _, _, warnings2 = validate_history_and_horizon(const_non_zero, 30)
    assert "SHORT_HISTORY" not in warnings2
    assert "SPARSE_HISTORY" not in warnings2
    assert "CONSTANT_HISTORY" in warnings2

    # Varied 35 days: short, not sparse, not constant
    varied_35 = make_history(35, value_fn=lambda i: (i + 1) * 1000)
    _, _, warnings3 = validate_history_and_horizon(varied_35, 7)
    assert warnings3 == ["SHORT_HISTORY"]


def test_no_target_leakage():
    dates = [datetime.date(2026, 1, 1) + datetime.timedelta(days=i) for i in range(15)]
    values = [float(i * 10) for i in range(15)]
    X, y = build_training_matrix(dates, values)

    # For index t=7:
    # Target y[0] is values[7] = 70.0
    assert y[0] == 70.0
    # Features for t=7:
    # lag1 = values[6] = 60.0
    # lag2 = values[5] = 50.0
    # lag7 = values[0] = 0.0
    # mean7 = mean(0..6) = (0+10+20+30+40+50+60)/7 = 30.0
    assert X[0, 0] == 60.0
    assert X[0, 1] == 50.0
    assert X[0, 2] == 0.0
    assert X[0, 3] == 30.0
    # Day t=7 value (70.0) must NOT be present in X[0]
    assert 70.0 not in X[0]


def test_signed_cash_flow_predictions():
    # History with negative NetCF values
    history = make_history(40, value_fn=lambda i: -50_000 + (i % 5) * 5_000)
    dates, vals, _ = validate_history_and_horizon(history, 7)
    rubles = [v / 100.0 for v in vals]

    results = run_forecast(dates, rubles, 7)
    assert len(results) == 7
    # Verify predictions are negative (signed permitted, not clipped to 0)
    for date_str, minor in results:
        assert minor < 0


def test_exactly_h_days_returned_consecutive():
    start_date = datetime.date(2026, 2, 1)
    history = make_history(
        35, start_date=start_date, value_fn=lambda i: 20_000 + i * 500
    )
    dates, vals, _ = validate_history_and_horizon(history, 30)
    rubles = [v / 100.0 for v in vals]

    last_history_date = dates[-1]
    results = run_forecast(dates, rubles, 30)
    assert len(results) == 30

    curr_expected = last_history_date + datetime.timedelta(days=1)
    for date_str, val in results:
        d = datetime.date.fromisoformat(date_str)
        assert d == curr_expected
        curr_expected += datetime.timedelta(days=1)
        assert isinstance(val, int)


def test_rounding_half_up():
    assert quantize_rubles_to_minor(12.345) == 1235
    assert quantize_rubles_to_minor(12.344) == 1234
    assert quantize_rubles_to_minor(-12.345) == -1235
    assert quantize_rubles_to_minor(-12.344) == -1234
    # Test precision preventing double rounding (e.g. 1.2349999 -> 123 cents, not 124 cents)
    assert quantize_rubles_to_minor(1.2349999) == 123
    assert quantize_rubles_to_minor(-1.2349999) == -123


def test_holdout_synthetic_no_random_split():
    eval_res = evaluate_holdout_synthetic(total_days=100, horizon_days=30)
    assert eval_res["train_days"] == 70
    assert eval_res["horizon_days"] == 30
    assert "hgb" in eval_res
    assert "seasonal_naive" in eval_res
    assert eval_res["hgb"]["mae_rubles"] >= 0.0
    assert eval_res["seasonal_naive"]["mae_rubles"] >= 0.0
