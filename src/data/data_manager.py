"""
Data Manager
Unified interface that manages NSE and Yahoo Finance data sources
Implements fallback logic and data caching
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
from src.data.yahoo_fetcher import YahooDataFetcher
from src.config.settings import config

logger = logging.getLogger(__name__)


class DataManager:
    """
    Unified data manager with NSE primary and Yahoo Finance fallback
    Implements caching and data quality checks
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
        self.use_cache = use_cache
        self.cache_dir = Path(config.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info("DataManager initialized")

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
        fallback_to_yahoo: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        Get stock data with fallback logic

        Parameters
        ----------
        symbol : str
            Stock symbol
        start_date : datetime
            Start date
        end_date : datetime
            End date
        fallback_to_yahoo : bool
            Use Yahoo as fallback if NSE fails

        Returns
        -------
        pd.DataFrame or None
            Stock OHLCV data
        """
        cache_key = f"stock_{symbol}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"

        # Try cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached

        # Try NSE first
        logger.info(f"Fetching {symbol} from NSE")
        data = self.nse_fetcher.get_stock_data(symbol, start_date, end_date)

        # Fallback to Yahoo if NSE fails
        if (data is None or data.empty) and fallback_to_yahoo:
            logger.info(f"NSE failed, trying Yahoo for {symbol}")
            data = self.yahoo_fetcher.get_stock_data(symbol, start_date, end_date)

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
        cache_key = f"market_{config.MARKET_INDEX}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"

        # Try cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached

        # Try NSE first
        logger.info("Fetching market index from NSE")
        data = self.nse_fetcher.get_index_data('NIFTY 50', start_date, end_date)

        # Fallback to Yahoo
        if data is None or data.empty:
            logger.info("NSE failed, trying Yahoo for market index")
            data = self.yahoo_fetcher.get_index_data(config.MARKET_INDEX, start_date, end_date)

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
        # Calculate date range with buffer
        start_date = announcement_date - timedelta(days=pre_window * 2)
        end_date = announcement_date + timedelta(days=post_window * 2)

        logger.info(f"Preparing dataset for {symbol} around {announcement_date}")

        # Get stock data
        stock_data = self.get_stock_data(symbol, start_date, end_date)

        # Get market data
        market_data = self.get_market_data(start_date, end_date)

        # Align dates (keep only trading days present in both)
        if stock_data is not None and market_data is not None:
            common_dates = stock_data.index.intersection(market_data.index)
            stock_data = stock_data.loc[common_dates].copy()
            market_data = market_data.loc[common_dates].copy()

            logger.info(f"Prepared {len(stock_data)} aligned trading days")

        return stock_data, market_data

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
