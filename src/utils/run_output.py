"""
Structured run output directories: datetime + symbol + announcement + data range.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd


def _sanitize_symbol(symbol: str, max_len: int = 24) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "", (symbol or "UNK").upper())
    return s[:max_len] if len(s) > max_len else s


def build_run_folder_name(
    symbol: str,
    announcement_date: Union[datetime, pd.Timestamp, str],
    data_index: pd.Index,
    run_timestamp: Optional[str] = None,
) -> str:
    """
    Build a filesystem-safe folder name:

        {timestamp}_{SYMBOL}_ann{YYYY-MM-DD}_{dataStart}_to_{dataEnd}

    Parameters
    ----------
    symbol : str
        Ticker (e.g. SMLMAH)
    announcement_date : datetime-like
        Earnings / event date used in the study
    data_index : pd.Index
        Aligned stock/index date index (defines the price sample range)
    run_timestamp : str, optional
        If provided (e.g. one value for an entire batch), reused so runs group together
    """
    ts = run_timestamp or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    sym = _sanitize_symbol(symbol)
    ann = pd.Timestamp(announcement_date).strftime("%Y-%m-%d")
    tmin = pd.Timestamp(data_index.min()).strftime("%Y-%m-%d")
    tmax = pd.Timestamp(data_index.max()).strftime("%Y-%m-%d")
    return f"{ts}_{sym}_ann{ann}_{tmin}_to_{tmax}"


def resolve_run_output_directory(
    output_base: Union[str, Path],
    symbol: str,
    announcement_date: Union[datetime, pd.Timestamp, str],
    data_index: pd.Index,
    run_timestamp: Optional[str] = None,
) -> Path:
    """
    Join output_base with a single run subfolder.
    """
    base = Path(output_base).expanduser().resolve()
    name = build_run_folder_name(
        symbol, announcement_date, data_index, run_timestamp=run_timestamp
    )
    return base / name
