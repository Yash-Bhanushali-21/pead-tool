# Data layer: pluggable OHLCV sources + façade.
# Prefer: ``from src.data.data_manager import DataManager``
#         ``from src.data.ohlcv_source import OHLCVSource``
# Concrete fetchers: ``nse_fetcher``, ``yahoo_fetcher``, ``jugaad_fetcher``.

from src.data.data_manager import DataManager
from src.data.ohlcv_source import OHLCVSource

__all__ = ["DataManager", "OHLCVSource"]
