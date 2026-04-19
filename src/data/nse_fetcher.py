"""
NSE Data Fetcher
Handles data fetching from NSE using the nse package
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import logging
from nse import NSE

from src.utils.time_compat import to_calendar_date

logger = logging.getLogger(__name__)


class NSEDataFetcher:
    """Fetch data from NSE for equity and announcements."""

    #: Slug for logs and :class:`~src.data.ohlcv_source.OHLCVSource` registration.
    SOURCE_ID = "nse"

    def __init__(self, download_folder: str = './data/nse_downloads'):
        """
        Initialize NSE connection

        Parameters
        ----------
        download_folder : str
            Folder to store NSE downloaded files
        """
        try:
            # Create download folder if it doesn't exist
            import os
            os.makedirs(download_folder, exist_ok=True)

            # Initialize NSE with download folder
            self.nse = NSE(download_folder=download_folder)
            logger.info(f"NSE connection established (download_folder: {download_folder})")
        except Exception as e:
            logger.warning(f"Failed to initialize NSE: {e}")
            logger.warning("NSE data source unavailable, will use Yahoo Finance fallback")
            self.nse = None

    def get_recent_announcements(self, n: int = 10) -> pd.DataFrame:
        """
        Get recent corporate announcements

        NOTE: NSE library API is limited. This attempts multiple methods
        but may return empty DataFrame if none work.

        Parameters
        ----------
        n : int
            Number of recent announcements to fetch

        Returns
        -------
        pd.DataFrame
            DataFrame with announcement details (may be empty)
        """
        if self.nse is None:
            logger.warning("NSE not available, returning empty announcements")
            return pd.DataFrame()

        try:
            logger.info(f"Attempting to fetch {n} announcements from NSE")

            # Try different possible method names
            announcements = None

            if hasattr(self.nse, 'get_corporate_announcements'):
                announcements = self.nse.get_corporate_announcements()
            elif hasattr(self.nse, 'announcements'):
                announcements = self.nse.announcements()
            elif hasattr(self.nse, 'get_announcements'):
                announcements = self.nse.get_announcements()
            else:
                logger.warning("NSE library doesn't have announcement methods")
                return pd.DataFrame()

            if announcements is None or len(announcements) == 0:
                logger.warning("No announcements returned from NSE")
                return pd.DataFrame()

            # Convert to DataFrame if not already
            if not isinstance(announcements, pd.DataFrame):
                announcements = pd.DataFrame(announcements)

            # Filter for earnings-related announcements
            earnings_keywords = [
                'result', 'earnings', 'financial', 'quarterly',
                'annual', 'profit', 'loss', 'q1', 'q2', 'q3', 'q4'
            ]

            # Create a filter for earnings announcements
            announcements['is_earnings'] = announcements.apply(
                lambda row: any(
                    keyword in str(row).lower()
                    for keyword in earnings_keywords
                ),
                axis=1
            )

            earnings_announcements = announcements[
                announcements['is_earnings']
            ].head(n).copy()

            # Standardize column names
            if 'symbol' in earnings_announcements.columns:
                earnings_announcements['SYMBOL'] = earnings_announcements['symbol']
            if 'an_dt' in earnings_announcements.columns:
                earnings_announcements['ANNOUNCEMENT_DATE'] = pd.to_datetime(
                    earnings_announcements['an_dt']
                )
            if 'desc' in earnings_announcements.columns:
                earnings_announcements['DESCRIPTION'] = earnings_announcements['desc']
            if 'attchmntFile' in earnings_announcements.columns:
                earnings_announcements['ATTACHMENT_URL'] = earnings_announcements['attchmntFile']

            logger.info(f"Found {len(earnings_announcements)} earnings announcements")
            return earnings_announcements

        except Exception as e:
            logger.error(f"Error fetching announcements: {e}")
            return pd.DataFrame()

    def get_stock_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Get historical stock data for a symbol

        Parameters
        ----------
        symbol : str
            Stock symbol (e.g., 'RELIANCE')
        start_date : datetime
            Start date for data
        end_date : datetime
            End date for data

        Returns
        -------
        pd.DataFrame or None
            DataFrame with OHLCV data
        """
        if self.nse is None:
            logger.warning("NSE not available, returning None for stock data")
            return None

        try:
            fd = to_calendar_date(start_date)
            td = to_calendar_date(end_date)
            logger.info(
                "data_fetch source=nse kind=equity_ohlcv nse_symbol=%s "
                "api=nse.fetch_equity_historical_data from_date=%s to_date=%s",
                symbol,
                fd,
                td,
            )

            # NSE package expects datetime.date objects (see fetch_equity_historical_data docs).
            data = self.nse.fetch_equity_historical_data(
                symbol=symbol,
                from_date=fd,
                to_date=td,
            )

            if data is None or len(data) == 0:
                logger.warning(
                    "data_fetch source=nse kind=equity_ohlcv nse_symbol=%s result=empty "
                    "from_date=%s to_date=%s",
                    symbol,
                    fd,
                    td,
                )
                return None

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Standardize column names
            column_mapping = {
                'CH_TIMESTAMP': 'Date',
                'CH_TRADE_HIGH_PRICE': 'High',
                'CH_TRADE_LOW_PRICE': 'Low',
                'CH_OPENING_PRICE': 'Open',
                'CH_CLOSING_PRICE': 'Close',
                'CH_TOT_TRADED_QTY': 'Volume',
                'CH_TOT_TRADED_VAL': 'Value',
                'VWAP': 'VWAP'
            }

            # Rename columns that exist
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df.rename(columns={old_col: new_col}, inplace=True)

            # Ensure Date column exists and is datetime
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)

            # Sort by date
            df.sort_index(inplace=True)

            if "Close" not in df.columns:
                logger.warning(
                    "data_fetch source=nse kind=equity_ohlcv nse_symbol=%s result=invalid "
                    "reason=no_close_after_column_map",
                    symbol,
                )
                return None

            # Calculate returns
            df["Return"] = df["Close"].pct_change()

            idx = df.index
            logger.info(
                "data_fetch source=nse kind=equity_ohlcv nse_symbol=%s result=ok rows=%d "
                "bar_first=%s bar_last=%s",
                symbol,
                len(df),
                pd.Timestamp(idx.min()).date().isoformat() if len(idx) else None,
                pd.Timestamp(idx.max()).date().isoformat() if len(idx) else None,
            )
            return df

        except Exception as e:
            logger.error(
                "data_fetch source=nse kind=equity_ohlcv nse_symbol=%s api=fetch_equity_historical_data "
                "error=%s",
                symbol,
                e,
                exc_info=True,
            )
            return None

    def get_company_info(self, symbol: str) -> Dict:
        """
        Get company information

        Parameters
        ----------
        symbol : str
            Stock symbol

        Returns
        -------
        dict
            Company information
        """
        if self.nse is None:
            logger.warning("NSE not available, returning empty company info")
            return {}

        try:
            logger.info(
                "data_fetch source=nse kind=company_quote nse_symbol=%s api=nse.quote",
                symbol,
            )
            # Correct method name: quote or equityQuote
            info = self.nse.quote(symbol)
            return info if info else {}
        except Exception as e:
            logger.error(
                "data_fetch source=nse kind=company_quote nse_symbol=%s error=%s",
                symbol,
                e,
                exc_info=True,
            )
            return {}

    def get_index_data(
        self,
        index: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Get index data (e.g., NIFTY 50)

        Parameters
        ----------
        index : str
            Index name (e.g., 'NIFTY 50')
        start_date : datetime
            Start date
        end_date : datetime
            End date

        Returns
        -------
        pd.DataFrame or None
            Index data
        """
        if self.nse is None:
            logger.warning("NSE not available, returning None for index data")
            return None

        try:
            fd = to_calendar_date(start_date)
            td = to_calendar_date(end_date)
            logger.info(
                "data_fetch source=nse kind=index_ohlcv index_name=%s "
                "api=nse.fetch_historical_index_data from_date=%s to_date=%s",
                index,
                fd,
                td,
            )

            # First positional / keyword is ``index`` (not ``symbol``); dates must be ``date``.
            data = self.nse.fetch_historical_index_data(
                index,
                from_date=fd,
                to_date=td,
            )

            if data:
                df = pd.DataFrame(data)
                if 'CH_TIMESTAMP' in df.columns:
                    df['Date'] = pd.to_datetime(df['CH_TIMESTAMP'])
                    df.set_index('Date', inplace=True)
                if 'CH_CLOSING_PRICE' in df.columns:
                    df['Close'] = df['CH_CLOSING_PRICE']
                    df['Return'] = df['Close'].pct_change()
                idx = df.index
                logger.info(
                    "data_fetch source=nse kind=index_ohlcv index_name=%s result=ok rows=%d "
                    "bar_first=%s bar_last=%s",
                    index,
                    len(df),
                    pd.Timestamp(idx.min()).date().isoformat() if len(idx) else None,
                    pd.Timestamp(idx.max()).date().isoformat() if len(idx) else None,
                )
                return df

            logger.warning(
                "data_fetch source=nse kind=index_ohlcv index_name=%s result=empty from_date=%s to_date=%s",
                index,
                fd,
                td,
            )
            return None

        except Exception as e:
            logger.error(
                "data_fetch source=nse kind=index_ohlcv index_name=%s error=%s",
                index,
                e,
                exc_info=True,
            )
            return None

    def get_corporate_actions(self, symbol: str) -> pd.DataFrame:
        """
        Get corporate actions (dividends, splits, bonuses)

        Parameters
        ----------
        symbol : str
            Stock symbol

        Returns
        -------
        pd.DataFrame
            Corporate actions data
        """
        if self.nse is None:
            logger.warning("NSE not available, returning empty corporate actions")
            return pd.DataFrame()

        try:
            logger.info(
                "data_fetch source=nse kind=corporate_actions nse_symbol=%s api=nse.get_corporate_actions",
                symbol,
            )
            actions = self.nse.get_corporate_actions(symbol)
            if actions:
                return pd.DataFrame(actions)
            return pd.DataFrame()
        except Exception as e:
            logger.error(
                "data_fetch source=nse kind=corporate_actions nse_symbol=%s error=%s",
                symbol,
                e,
                exc_info=True,
            )
            return pd.DataFrame()
