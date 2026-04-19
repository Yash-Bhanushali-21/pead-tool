"""Align a market index close series to a stock OHLCV index (relative strength)."""
from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd

from src.config.config import CONFIG


def aligned_market_index_close(
    data_manager,
    stock_data: pd.DataFrame,
    *,
    index_symbol: Optional[str] = None,
) -> Tuple[Optional[pd.Series], str]:
    """
    Fetch ``index_symbol`` (default ``MARKET_INDEX`` / ``^NSEI``) over the stock window and
    reindex to ``stock_data`` dates (ffill/bfill).

    Uses :meth:`~src.data.data_manager.DataManager.get_market_data` for the configured
    NIFTY/Yahoo index — not :meth:`~src.data.data_manager.DataManager.get_stock_data`, so
    Yahoo tickers like ``^NSEI`` are not mangled to ``^NSEI.NS``.
    """
    sym = str(index_symbol or CONFIG.get("MARKET_INDEX") or "^NSEI")
    default_idx = str(CONFIG.get("MARKET_INDEX") or "^NSEI")
    try:
        start = pd.Timestamp(stock_data.index.min()).to_pydatetime()
        end = pd.Timestamp(stock_data.index.max()).to_pydatetime()
        if sym == default_idx:
            bdf = data_manager.get_market_data(start, end)
        elif sym.startswith("^"):
            bdf = data_manager.yahoo_fetcher.get_index_data(sym, start, end)
        else:
            bdf = data_manager.get_stock_data(sym, start, end)
    except Exception:
        return None, sym
    if bdf is None or bdf.empty or "Close" not in bdf.columns:
        return None, sym
    bdf = data_manager._strip_tz_index(bdf)
    bc = bdf["Close"].astype(float)
    aligned = bc.reindex(stock_data.index).ffill().bfill()
    if bool(aligned.isna().all()):
        return None, sym
    return aligned, sym
