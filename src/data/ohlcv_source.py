"""
Pluggable OHLCV sources for equities.

Implement :class:`OHLCVSource` on any vendor (NSE, Yahoo, Zerodha, vendor files, …) and wire it
through :class:`~src.data.data_manager.DataManager` merge / fallback logic.

Concrete classes should set ``SOURCE_ID`` (short slug) for logs and config.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class OHLCVSource(Protocol):
    """
    Minimal interface for historical stock OHLCV.

    Expected columns after normalization elsewhere: ``Open``, ``High``, ``Low``, ``Close``,
    ``Volume``; index calendar dates. ``None`` or empty means unavailable.
    """

    def get_stock_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        ...
