"""Unit tests for multi-vendor OHLCV merge / window-coverage helpers."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.data.data_manager import DataManager


def test_ohlcv_missing_request_start_empty() -> None:
    assert DataManager._ohlcv_missing_request_start(None, datetime(2021, 1, 1)) is True
    assert DataManager._ohlcv_missing_request_start(pd.DataFrame(), datetime(2021, 1, 1)) is True


def test_ohlcv_missing_request_start_truncated_history() -> None:
    idx = pd.date_range("2025-10-30", periods=3, freq="B")
    df = pd.DataFrame(
        {"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1.0},
        index=idx,
    )
    assert DataManager._ohlcv_missing_request_start(df, datetime(2021, 1, 1)) is True


def test_ohlcv_missing_request_start_within_slack() -> None:
    idx = pd.DatetimeIndex([pd.Timestamp("2025-01-06")])
    df = pd.DataFrame(
        {"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1.0},
        index=idx,
    )
    assert DataManager._ohlcv_missing_request_start(df, datetime(2025, 1, 1), slack_calendar_days=14) is False


def test_merge_ohlcv_priority_last_vendor_wins_overlap() -> None:
    y = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [10.0], "Volume": [1.0]},
        index=[pd.Timestamp("2025-01-02")],
    )
    n = pd.DataFrame(
        {"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [20.0], "Volume": [2.0]},
        index=[pd.Timestamp("2025-01-02")],
    )
    merged = DataManager._merge_ohlcv_priority(y, n)
    assert merged is not None
    assert merged.loc[pd.Timestamp("2025-01-02"), "Close"] == 20.0


def test_merge_ohlcv_priority_concatenates_non_overlapping() -> None:
    y = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [1.0]},
        index=[pd.Timestamp("2024-06-03")],
    )
    n = pd.DataFrame(
        {"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [2.0]},
        index=[pd.Timestamp("2025-06-03")],
    )
    merged = DataManager._merge_ohlcv_priority(y, n)
    assert merged is not None
    assert len(merged) == 2


def test_clip_ohlcv_calendar_window() -> None:
    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    df = pd.DataFrame(
        {"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1.0, "Return": 0.0},
        index=idx,
    )
    clipped = DataManager._clip_ohlcv_calendar_window(df, datetime(2024, 1, 3), datetime(2024, 1, 5))
    assert clipped is not None
    assert clipped.index.min() >= pd.Timestamp("2024-01-03")
    assert clipped.index.max() <= pd.Timestamp("2024-01-05")
