"""
NSE historical OHLCV via ``jugaad-data`` (NSE website / bhav-style pipeline).

Used when :mod:`nsepython`-backed NSE fetch and Yahoo (:mod:`yfinance`, see
https://github.com/ranaroussi/yfinance ) both fail or return no rows.

``jugaad-data`` targets the current NSE site (see
https://github.com/jugaad-py/jugaad-data ). Respect NSE rate limits; the library
ships caching — do not bypass with tight loops.

This module is optional at runtime: if ``jugaad-data`` is not installed, calls
return ``None`` without error.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import pandas as pd

from src.utils.time_compat import to_calendar_date

logger = logging.getLogger(__name__)

_jugaad_import_warning_emitted = False


def _nse_symbol_base(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.endswith(".NS"):
        return s[:-3]
    if s.endswith(".BO"):
        return s[:-3]
    return s


def _canon_col(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.strip().upper())


def _pick_col(df: pd.DataFrame, canon_options: tuple[str, ...]) -> Optional[str]:
    """First column whose canonical name matches one of ``canon_options`` (NSE CH_* preferred when listed first)."""
    for want in canon_options:
        for c in df.columns:
            if _canon_col(c) == want:
                return c
    return None


def _normalize_jugaad_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Map NSE/jugaad column labels to the OHLCV schema used elsewhere in the repo."""
    if df is None or df.empty:
        return df

    d_src = _pick_col(df, ("DATE", "CHTIMESTAMP", "TRADEDATE"))
    if d_src is not None:
        dates = pd.to_datetime(df[d_src], errors="coerce")
    elif isinstance(df.index, pd.DatetimeIndex):
        dates = pd.to_datetime(df.index, errors="coerce")
    else:
        logger.warning("jugaad-data frame has no recognizable date column")
        return pd.DataFrame()

    o_src = _pick_col(df, ("CHOPENINGPRICE", "OPEN"))
    h_src = _pick_col(df, ("CHTRADEHIGHPRICE", "HIGH"))
    l_src = _pick_col(df, ("CHTRADELOWPRICE", "LOW"))
    c_src = _pick_col(df, ("CHCLOSINGPRICE", "CLOSE", "LTP"))
    v_src = _pick_col(df, ("CHTOTTRADEDQTY", "VOLUME", "TOTTRDQTY"))

    if c_src is None:
        logger.warning("jugaad-data frame has no close column")
        return pd.DataFrame()

    out = pd.DataFrame(
        {
            "Date": dates,
            "Open": pd.to_numeric(df[o_src], errors="coerce") if o_src else pd.NA,
            "High": pd.to_numeric(df[h_src], errors="coerce") if h_src else pd.NA,
            "Low": pd.to_numeric(df[l_src], errors="coerce") if l_src else pd.NA,
            "Close": pd.to_numeric(df[c_src], errors="coerce"),
            "Volume": pd.to_numeric(df[v_src], errors="coerce") if v_src else 0.0,
        }
    )

    out = out.dropna(subset=["Date", "Close"])
    if out.empty:
        return pd.DataFrame()

    for col in ("Open", "High", "Low"):
        if out[col].isna().all():
            out[col] = out["Close"]
        else:
            out[col] = out[col].fillna(out["Close"])

    out["Volume"] = out["Volume"].fillna(0.0)

    out = out.set_index("Date").sort_index()
    out["Return"] = out["Close"].pct_change()
    out.index.name = "Date"
    return out


class JugaadDataFetcher:
    """Fetch NSE equity history when other paths fail (optional dependency)."""

    def __init__(self, series: str = "EQ") -> None:
        self.series = series

    def get_stock_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        global _jugaad_import_warning_emitted
        try:
            from jugaad_data.nse import stock_df  # type: ignore[import-untyped]
        except ImportError:
            if not _jugaad_import_warning_emitted:
                logger.warning(
                    "jugaad-data is not importable (``pip install jugaad-data``). "
                    "NSE-site OHLCV backfill is disabled; Yahoo-only repair may be insufficient for some symbols."
                )
                _jugaad_import_warning_emitted = True
            return None

        sym = _nse_symbol_base(symbol)
        if not sym:
            return None

        fd = to_calendar_date(start_date)
        td = to_calendar_date(end_date)
        if fd > td:
            return None

        try:
            logger.info("Fetching %s from jugaad-data (NSE) %s .. %s", sym, fd, td)
            raw = stock_df(symbol=sym, from_date=fd, to_date=td, series=self.series)
        except Exception as e:
            logger.warning("jugaad-data fetch failed for %s: %s", sym, e)
            return None

        if raw is None or raw.empty:
            logger.warning("jugaad-data returned no rows for %s", sym)
            return None

        df = _normalize_jugaad_ohlcv(raw)
        if df is None or df.empty:
            logger.warning("jugaad-data normalization produced empty frame for %s", sym)
            return None

        logger.info("Fetched %d rows from jugaad-data for %s", len(df), sym)
        return df
