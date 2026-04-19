"""
Data Manager
Unified façade over pluggable :class:`~src.data.ohlcv_source.OHLCVSource` implementations
(NSE → Yahoo → jugaad for stock OHLCV), with merge rules and caching.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging
import pickle
import os
from pathlib import Path

from src.data.nse_fetcher import NSEDataFetcher
from src.data.ohlcv_source import OHLCVSource
from src.data.yahoo_fetcher import YahooDataFetcher
from src.data.jugaad_fetcher import JugaadDataFetcher
from src.config.config import config
from src.utils.time_compat import to_calendar_date

logger = logging.getLogger(__name__)

# Bumped when merge / coverage semantics change (invalidates pickles that stored vendor-only windows).
_STOCK_OHLCV_CACHE_PREFIX = "stock_ohlcv_merged_v2"
_MARKET_OHLCV_CACHE_PREFIX = "market_ohlcv_merged_v2"

# When multiple OHLCV frames are merged, duplicate calendar days keep the **last** argument to
# ``_merge_ohlcv_priority`` (highest priority last). Current call order: Yahoo → Jugaad → NSE.
_OHLCV_MERGE_ORDER_STOCK = ("yahoo", "jugaad", "nse")


class DataManager:
    """
    Unified data manager: NSE (nsepython) → Yahoo (yfinance) → optional jugaad-data (NSE site).

    Stock OHLCV sources implement :class:`~src.data.ohlcv_source.OHLCVSource`; see
    ``self.ohlcv_sources`` for the registered list. Merge priority for overlapping days:
    last in ``_OHLCV_MERGE_ORDER_STOCK`` wins (NSE overwrites earlier vendors).

    See :class:`~src.data.yahoo_fetcher.YahooDataFetcher` and :class:`~src.data.jugaad_fetcher.JugaadDataFetcher`.
    """

    def __init__(self, use_cache: bool = True):
        """
        Initialize data manager

        Parameters
        ----------
        use_cache : bool
            Whether to use cached data
        """
        self.nse_fetcher = NSEDataFetcher()
        self.yahoo_fetcher = YahooDataFetcher()
        self.jugaad_fetcher = JugaadDataFetcher()
        #: Registered stock OHLCV backends (id, source) — add new vendors here after implementing ``OHLCVSource``.
        self.ohlcv_sources: tuple[tuple[str, OHLCVSource], ...] = (
            (self.nse_fetcher.SOURCE_ID, self.nse_fetcher),
            (self.yahoo_fetcher.SOURCE_ID, self.yahoo_fetcher),
            (self.jugaad_fetcher.SOURCE_ID, self.jugaad_fetcher),
        )
        self.use_cache = use_cache
        self.cache_dir = Path(config.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info("DataManager initialized")

    @staticmethod
    def _ohlcv_missing_request_start(
        df: Optional[pd.DataFrame],
        start_date: datetime,
        slack_calendar_days: int = 14,
    ) -> bool:
        """
        True when the frame has no rows, or its first bar is materially later than the
        inclusive calendar ``start_date`` (weekends / thin listings — use slack).
        """
        if df is None or df.empty:
            return True
        work = DataManager._strip_tz_index(df)
        if work.index.size == 0:
            return True
        first = pd.Timestamp(to_calendar_date(work.index.min()))
        want = pd.Timestamp(to_calendar_date(start_date))
        return bool(first > want + timedelta(days=slack_calendar_days))

    @staticmethod
    def _merge_ohlcv_priority(*candidates: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """
        Stack OHLCV from multiple vendors; duplicate calendar days keep the **last** frame
        (NSE last in call order wins on overlap — Yahoo/jugaad fill history, NSE refines recent).
        """
        pieces: List[pd.DataFrame] = []
        for raw in candidates:
            if raw is None or raw.empty:
                continue
            part = DataManager._strip_tz_index(raw.copy())
            part.index = pd.to_datetime(part.index, errors="coerce").normalize()
            part = part[part.index.notna()]
            if part.empty or "Close" not in part.columns:
                continue
            for need in ("Open", "High", "Low"):
                if need not in part.columns:
                    part[need] = part["Close"]
                else:
                    part[need] = part[need].where(part[need].notna(), part["Close"])
            if "Volume" not in part.columns:
                part["Volume"] = 0.0
            else:
                part["Volume"] = part["Volume"].fillna(0.0)
            pieces.append(part[["Open", "High", "Low", "Close", "Volume"]].copy())

        if not pieces:
            return None

        merged = pd.concat(pieces).sort_index()
        merged = merged[~merged.index.duplicated(keep="last")]
        merged["Return"] = merged["Close"].pct_change()
        merged.index.name = "Date"
        return merged

    @staticmethod
    def _clip_ohlcv_calendar_window(
        df: Optional[pd.DataFrame],
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        if df is None or df.empty:
            return df
        cal_s = pd.Timestamp(to_calendar_date(start_date))
        cal_e = pd.Timestamp(to_calendar_date(end_date))
        out = df.loc[(df.index >= cal_s) & (df.index <= cal_e)].copy()
        if out.empty:
            return out
        out["Return"] = out["Close"].pct_change()
        return out

    def _get_cache_path(self, key: str) -> Path:
        """Generate cache file path"""
        return self.cache_dir / f"{key}.pkl"

    def _load_from_cache(self, key: str) -> Optional[any]:
        """Load data from cache"""
        if not self.use_cache:
            return None

        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    data = pickle.load(f)
                logger.info(f"Loaded from cache: {key}")
                return data
            except Exception as e:
                logger.warning(f"Failed to load cache {key}: {e}")
        return None

    def _save_to_cache(self, key: str, data: any) -> None:
        """Save data to cache"""
        if not self.use_cache:
            return

        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"Saved to cache: {key}")
        except Exception as e:
            logger.warning(f"Failed to save cache {key}: {e}")

    def get_recent_announcements(self, n: int = 10) -> pd.DataFrame:
        """
        Get recent earnings announcements

        Uses curated list of major stocks since NSE API is unreliable.

        Parameters
        ----------
        n : int
            Number of stocks to analyze

        Returns
        -------
        pd.DataFrame
            Stock symbols for analysis
        """
        cache_key = f"announcements_{n}_{datetime.now().strftime('%Y%m%d')}"

        # Try cache first
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached

        # Try NSE
        announcements = self.nse_fetcher.get_recent_announcements(n)

        # Validate announcement dates - reject future dates
        if not announcements.empty and 'ANNOUNCEMENT_DATE' in announcements.columns:
            now = pd.Timestamp.now()
            future_count = (pd.to_datetime(announcements['ANNOUNCEMENT_DATE']) > now).sum()
            if future_count > 0:
                logger.warning(
                    f"NSE returned {future_count} announcements with future dates, "
                    f"using curated list instead"
                )
                announcements = pd.DataFrame()

        # Fallback to curated list
        if announcements.empty:
            logger.info("Using curated stock list")
            announcements = self._get_curated_stocks(n)

        if not announcements.empty:
            self._save_to_cache(cache_key, announcements)

        return announcements

    def _get_curated_stocks(self, n: int = 10) -> pd.DataFrame:
        """
        Get curated list of major Indian stocks with Q2 FY26 announcement dates
        """
        stocks = [
            # Q2 FY26 results (Oct-Nov 2025) - recent but with post-announcement data
            {'SYMBOL': 'TCS', 'DESCRIPTION': 'IT - TCS', 'ANNOUNCEMENT_DATE': datetime(2025, 10, 9)},
            {'SYMBOL': 'INFY', 'DESCRIPTION': 'IT - Infosys', 'ANNOUNCEMENT_DATE': datetime(2024, 10, 17)},
            {'SYMBOL': 'HDFCBANK', 'DESCRIPTION': 'Banking - HDFC', 'ANNOUNCEMENT_DATE': datetime(2024, 10, 19)},
            {'SYMBOL': 'RELIANCE', 'DESCRIPTION': 'Energy - Reliance', 'ANNOUNCEMENT_DATE': datetime(2024, 10, 14)},
            {'SYMBOL': 'ICICIBANK', 'DESCRIPTION': 'Banking - ICICI', 'ANNOUNCEMENT_DATE': datetime(2024, 10, 26)},
            {'SYMBOL': 'SBIN', 'DESCRIPTION': 'Banking - SBI', 'ANNOUNCEMENT_DATE': datetime(2024, 11, 2)},
            {'SYMBOL': 'MARUTI', 'DESCRIPTION': 'Auto - Maruti', 'ANNOUNCEMENT_DATE': datetime(2024, 10, 24)},
            {'SYMBOL': 'WIPRO', 'DESCRIPTION': 'IT - Wipro', 'ANNOUNCEMENT_DATE': datetime(2024, 10, 16)},
            {'SYMBOL': 'HCLTECH', 'DESCRIPTION': 'IT - HCL Tech', 'ANNOUNCEMENT_DATE': datetime(2024, 10, 14)},
            {'SYMBOL': 'SUNPHARMA', 'DESCRIPTION': 'Pharma - Sun', 'ANNOUNCEMENT_DATE': datetime(2024, 10, 30)},
        ]

        df = pd.DataFrame(stocks[:n])
        # Convert to pandas datetime
        df['ANNOUNCEMENT_DATE'] = pd.to_datetime(df['ANNOUNCEMENT_DATE'])

        logger.info(f"Using {len(df)} stocks with Q2 FY26 dates (Oct-Nov 2025)")
        return df

    def get_stock_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        fallback_to_yahoo: bool = True,
        fallback_to_jugaad: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        Get stock OHLCV with vendor merge.

        NSE is queried first. If NSE returns **no rows** or **starts too late** relative to
        ``start_date`` (see slack in :meth:`_ohlcv_missing_request_start`), Yahoo is fetched for
        the full window and merged (Yahoo then NSE; overlapping days keep NSE). If the merged
        series still lacks early coverage, ``jugaad-data`` is tried the same way.

        Parameters
        ----------
        symbol : str
            Stock symbol
        start_date : datetime
            Start date
        end_date : datetime
            End date
        fallback_to_yahoo : bool
            Pull Yahoo when NSE is empty or truncated at the head of the window.
        fallback_to_jugaad : bool
            Pull jugaad-data when NSE is short on history and Yahoo still does not reach the
            requested start (or Yahoo is empty). No-op if the package is not installed.

        Returns
        -------
        pd.DataFrame or None
            Stock OHLCV data
        """
        cache_key = (
            f"{_STOCK_OHLCV_CACHE_PREFIX}_{symbol}_"
            f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        )

        # Try cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            logger.info(
                "data_manager.get_stock_data cache=hit symbol=%s calendar_start=%s calendar_end=%s "
                "rows=%d",
                symbol,
                to_calendar_date(start_date),
                to_calendar_date(end_date),
                len(cached.index),
            )
            return cached

        logger.info(
            "data_manager.get_stock_data cache=miss symbol=%s calendar_start=%s calendar_end=%s "
            "flow=nse_then_conditional_yahoo_jugaad",
            symbol,
            to_calendar_date(start_date),
            to_calendar_date(end_date),
        )
        nse_df = self.nse_fetcher.get_stock_data(symbol, start_date, end_date)

        yahoo_df: Optional[pd.DataFrame] = None
        jugaad_df: Optional[pd.DataFrame] = None

        miss_nse = self._ohlcv_missing_request_start(nse_df, start_date)
        if miss_nse and fallback_to_yahoo:
            if nse_df is not None and not nse_df.empty:
                logger.info(
                    "data_manager.get_stock_data fallback=yahoo reason=nse_starts_late symbol=%s "
                    "nse_first_bar=%s requested_start=%s",
                    symbol,
                    to_calendar_date(nse_df.index.min()),
                    to_calendar_date(start_date),
                )
            else:
                logger.info(
                    "data_manager.get_stock_data fallback=yahoo reason=nse_empty symbol=%s "
                    "calendar_start=%s calendar_end=%s",
                    symbol,
                    to_calendar_date(start_date),
                    to_calendar_date(end_date),
                )
            yahoo_df = self.yahoo_fetcher.get_stock_data(symbol, start_date, end_date)

        # jugaad-data (NSE site): use when NSE is short on history *and* Yahoo did not deliver an
        # early enough first bar (empty Yahoo still triggers this — do not require a merge check).
        if miss_nse and fallback_to_jugaad:
            yahoo_still_short = yahoo_df is None or yahoo_df.empty or self._ohlcv_missing_request_start(
                yahoo_df, start_date
            )
            if yahoo_still_short:
                logger.info(
                    "data_manager.get_stock_data fallback=jugaad reason=yahoo_still_short_or_empty "
                    "symbol=%s calendar_start=%s calendar_end=%s",
                    symbol,
                    to_calendar_date(start_date),
                    to_calendar_date(end_date),
                )
                jugaad_df = self.jugaad_fetcher.get_stock_data(symbol, start_date, end_date)

        if (
            nse_df is not None
            and not nse_df.empty
            and not self._ohlcv_missing_request_start(nse_df, start_date)
        ):
            # NSE alone covers the requested start — keep any extra NSE columns (e.g. VWAP).
            data = self._clip_ohlcv_calendar_window(
                self._strip_tz_index(nse_df.copy()),
                start_date,
                end_date,
            )
        else:
            # Order must match _OHLCV_MERGE_ORDER_STOCK (last wins on duplicate index).
            data = self._merge_ohlcv_priority(yahoo_df, jugaad_df, nse_df)
            data = self._clip_ohlcv_calendar_window(data, start_date, end_date)

        if data is not None and not data.empty and self._ohlcv_missing_request_start(data, start_date):
            logger.warning(
                "OHLCV for %s still does not reach requested start %s (first bar %s) after "
                "NSE + Yahoo (+ jugaad when tried). Likely listing/IPO after the window, or all feeds truncated.",
                symbol,
                to_calendar_date(start_date),
                to_calendar_date(data.index.min()),
            )

        # Validate data quality
        if data is not None and not data.empty:
            data = self._validate_stock_data(data, symbol)
            if data is not None:
                self._save_to_cache(cache_key, data)

        return data

    def get_market_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Get market index data (NIFTY 50)

        Parameters
        ----------
        start_date : datetime
            Start date
        end_date : datetime
            End date

        Returns
        -------
        pd.DataFrame or None
            Market index data
        """
        cache_key = (
            f"{_MARKET_OHLCV_CACHE_PREFIX}_{config.MARKET_INDEX}_"
            f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        )

        # Try cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            logger.info(
                "data_manager.get_market_data cache=hit market_index_yahoo=%s calendar_start=%s "
                "calendar_end=%s rows=%d",
                config.MARKET_INDEX,
                to_calendar_date(start_date),
                to_calendar_date(end_date),
                len(cached.index),
            )
            return cached

        logger.info(
            "data_manager.get_market_data cache=miss nse_index_name=NIFTY 50 yahoo_index=%s "
            "calendar_start=%s calendar_end=%s flow=nse_then_yahoo_if_short",
            config.MARKET_INDEX,
            to_calendar_date(start_date),
            to_calendar_date(end_date),
        )
        nse_idx = self.nse_fetcher.get_index_data("NIFTY 50", start_date, end_date)

        yahoo_idx: Optional[pd.DataFrame] = None
        if self._ohlcv_missing_request_start(nse_idx, start_date):
            if nse_idx is not None and not nse_idx.empty:
                logger.info(
                    "data_manager.get_market_data fallback=yahoo reason=nse_index_starts_late "
                    "nse_first_bar=%s requested_start=%s yahoo_index=%s",
                    to_calendar_date(nse_idx.index.min()),
                    to_calendar_date(start_date),
                    config.MARKET_INDEX,
                )
            else:
                logger.info(
                    "data_manager.get_market_data fallback=yahoo reason=nse_index_empty "
                    "yahoo_index=%s calendar_start=%s calendar_end=%s",
                    config.MARKET_INDEX,
                    to_calendar_date(start_date),
                    to_calendar_date(end_date),
                )
            yahoo_idx = self.yahoo_fetcher.get_index_data(config.MARKET_INDEX, start_date, end_date)

        if (
            nse_idx is not None
            and not nse_idx.empty
            and not self._ohlcv_missing_request_start(nse_idx, start_date)
        ):
            data = self._clip_ohlcv_calendar_window(
                self._strip_tz_index(nse_idx.copy()),
                start_date,
                end_date,
            )
        else:
            data = self._merge_ohlcv_priority(yahoo_idx, nse_idx)
            data = self._clip_ohlcv_calendar_window(data, start_date, end_date)

        if data is not None and not data.empty:
            self._save_to_cache(cache_key, data)

        return data

    def _validate_stock_data(
        self,
        data: pd.DataFrame,
        symbol: str
    ) -> Optional[pd.DataFrame]:
        """
        Validate stock data quality

        Parameters
        ----------
        data : pd.DataFrame
            Stock data
        symbol : str
            Stock symbol

        Returns
        -------
        pd.DataFrame or None
            Validated data or None if quality issues
        """
        if data is None or data.empty:
            return None

        # Check for required columns
        required_cols = ['Close', 'Volume']
        if not all(col in data.columns for col in required_cols):
            logger.warning(f"Missing required columns for {symbol}")
            return None

        # Check for sufficient data points
        if len(data) < config.MIN_TRADING_DAYS:
            logger.warning(f"Insufficient data for {symbol}: {len(data)} rows")
            return None

        # Remove rows with missing Close prices
        original_len = len(data)
        data = data[data['Close'].notna()].copy()
        if len(data) < original_len:
            logger.warning(f"Removed {original_len - len(data)} rows with missing Close prices")

        # Check for data anomalies (extreme price movements)
        if 'Return' in data.columns:
            extreme_returns = data['Return'].abs() > 0.5  # 50% daily move
            if extreme_returns.any():
                logger.warning(f"Found {extreme_returns.sum()} extreme returns for {symbol}")

        return data

    def get_company_fundamentals(self, symbol: str) -> Dict:
        """
        Get company fundamental data

        Parameters
        ----------
        symbol : str
            Stock symbol

        Returns
        -------
        dict
            Fundamental metrics
        """
        cache_key = f"fundamentals_{symbol}_{datetime.now().strftime('%Y%m%d')}"

        # Try cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached

        # Get from NSE
        fundamentals = self.nse_fetcher.get_company_info(symbol)

        # Supplement with Yahoo data
        yahoo_info = self.yahoo_fetcher.get_company_info(symbol)
        fundamentals.update(yahoo_info)

        # Get financials from Yahoo
        financials = self.yahoo_fetcher.get_financials(symbol)
        fundamentals['financials'] = financials

        if fundamentals:
            self._save_to_cache(cache_key, fundamentals)

        return fundamentals

    def prepare_analysis_dataset(
        self,
        symbol: str,
        announcement_date: datetime,
        pre_window: int = 120,
        post_window: int = 90
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        Prepare complete dataset for PEAD analysis

        Parameters
        ----------
        symbol : str
            Stock symbol
        announcement_date : datetime
            Announcement date
        pre_window : int
            Trading days before announcement
        post_window : int
            Trading days after announcement

        Returns
        -------
        tuple
            (stock_data, market_data)
        """
        start_date, end_date = self.event_window_fetch_bounds(
            announcement_date, pre_window=pre_window, post_window=post_window
        )

        logger.info(f"Preparing dataset for {symbol} around {announcement_date}")

        # Get stock data
        stock_data = self.get_stock_data(symbol, start_date, end_date)

        # Get market data
        market_data = self.get_market_data(start_date, end_date)

        # Align dates (keep only trading days present in both)
        if stock_data is not None and market_data is not None:
            stock_data = self._strip_tz_index(stock_data)
            market_data = self._strip_tz_index(market_data)
            common_dates = stock_data.index.intersection(market_data.index)
            stock_data = stock_data.loc[common_dates].sort_index().copy()
            market_data = market_data.loc[common_dates].sort_index().copy()

            logger.info(f"Prepared {len(stock_data)} aligned trading days")

        return stock_data, market_data

    @staticmethod
    def event_window_fetch_bounds(
        announcement_date: datetime,
        pre_window: int = 120,
        post_window: int = 90,
    ) -> Tuple[datetime, datetime]:
        """
        Calendar span used by :meth:`prepare_analysis_dataset` and
        :meth:`get_stock_data_for_event_window` (wide window so thin tickers still get vendor history).
        """
        start_date = announcement_date - timedelta(days=max(400, pre_window * 3))
        end_date = announcement_date + timedelta(days=post_window * 2)
        return start_date, end_date

    def get_stock_data_for_event_window(
        self,
        symbol: str,
        announcement_date: datetime,
        pre_window: int = 120,
        post_window: int = 90,
    ) -> Optional[pd.DataFrame]:
        """
        Same calendar span as :meth:`prepare_analysis_dataset`, but **stock OHLCV only**
        (no index alignment). Use for technical snapshots when the market series is
        unnecessary or unavailable.
        """
        start_date, end_date = self.event_window_fetch_bounds(
            announcement_date, pre_window=pre_window, post_window=post_window
        )
        return self.get_stock_data(symbol, start_date, end_date)

    @staticmethod
    def _strip_tz_index(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Normalize to timezone-naive dates so stock/index series align (Yahoo often returns UTC)."""
        if df is None or df.empty:
            return df
        out = df.copy()
        if getattr(out.index, "tz", None) is not None:
            out.index = out.index.tz_convert(None)
        return out

    def clear_cache(self, older_than_days: int = 7) -> None:
        """
        Clear old cache files

        Parameters
        ----------
        older_than_days : int
            Remove cache files older than this many days
        """
        cutoff_time = datetime.now() - timedelta(days=older_than_days)
        removed = 0

        for cache_file in self.cache_dir.glob("*.pkl"):
            if datetime.fromtimestamp(cache_file.stat().st_mtime) < cutoff_time:
                cache_file.unlink()
                removed += 1

        logger.info(f"Cleared {removed} old cache files")
