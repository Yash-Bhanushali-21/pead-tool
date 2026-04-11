"""
Resolve earnings / event dates for NSE symbols (Yahoo + NSE + fallbacks).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def get_latest_announcement_date(symbol: str, data_manager) -> Optional[datetime]:
    """
    Auto-detect latest earnings announcement date for a symbol.
    Mirrors main.py logic without printing to stdout.
    """
    try:
        nse_announcements = data_manager.nse_fetcher.get_recent_announcements(n=100)
        if not nse_announcements.empty and "SYMBOL" in nse_announcements.columns:
            symbol_announcements = nse_announcements[
                nse_announcements["SYMBOL"].str.upper() == symbol.upper()
            ]
            if (
                not symbol_announcements.empty
                and "ANNOUNCEMENT_DATE" in symbol_announcements.columns
            ):
                latest = pd.to_datetime(symbol_announcements["ANNOUNCEMENT_DATE"]).max()
                if pd.notna(latest):
                    logger.info("Announcement date from NSE: %s", latest.date())
                    return latest

        ticker = yf.Ticker(f"{symbol}.NS")
        if hasattr(ticker, "earnings_dates") and ticker.earnings_dates is not None:
            earnings_dates = ticker.earnings_dates
            if not earnings_dates.empty:
                idx = earnings_dates.index
                now = (
                    pd.Timestamp.now(tz=idx.tz)
                    if getattr(idx, "tz", None) is not None
                    else pd.Timestamp.now()
                )
                past_earnings = earnings_dates[earnings_dates.index <= now]
                if not past_earnings.empty:
                    latest = past_earnings.index[0]
                    logger.info("Announcement date from Yahoo earnings_dates: %s", latest.date())
                    return latest

        if hasattr(ticker, "calendar") and ticker.calendar is not None:
            calendar = ticker.calendar
            if "Earnings Date" in calendar:
                earnings_date = pd.to_datetime(calendar["Earnings Date"])
                if pd.notna(earnings_date):
                    logger.info("Announcement date from Yahoo calendar: %s", earnings_date.date())
                    return earnings_date

        curated = data_manager._get_curated_stocks(n=20)
        if not curated.empty and "SYMBOL" in curated.columns:
            match = curated[curated["SYMBOL"].str.upper() == symbol.upper()]
            if not match.empty and "ANNOUNCEMENT_DATE" in match.columns:
                latest = pd.to_datetime(match["ANNOUNCEMENT_DATE"].iloc[0])
                logger.info("Announcement date from curated list: %s", latest.date())
                return latest

        return None
    except Exception as e:
        logger.warning("Auto-detect announcement date failed: %s", e)
        return None
