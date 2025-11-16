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

logger = logging.getLogger(__name__)


class NSEDataFetcher:
    """Fetch data from NSE for equity and announcements"""

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
            logger.error(f"Failed to initialize NSE: {e}")
            raise

    def get_recent_announcements(self, n: int = 10) -> pd.DataFrame:
        """
        Get recent corporate announcements

        Parameters
        ----------
        n : int
            Number of recent announcements to fetch

        Returns
        -------
        pd.DataFrame
            DataFrame with announcement details
        """
        try:
            logger.info(f"Fetching {n} recent announcements from NSE")

            # Get announcements - the NSE package provides this
            announcements = self.nse.get_corporate_announcements()

            if announcements is None or len(announcements) == 0:
                logger.warning("No announcements found")
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
        try:
            logger.info(f"Fetching stock data for {symbol} from {start_date} to {end_date}")

            # NSE package provides historical data
            data = self.nse.get_hist(
                symbol=symbol,
                from_date=start_date.strftime('%d-%m-%Y'),
                to_date=end_date.strftime('%d-%m-%Y')
            )

            if data is None or len(data) == 0:
                logger.warning(f"No data found for {symbol}")
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

            # Calculate returns
            df['Return'] = df['Close'].pct_change()

            logger.info(f"Fetched {len(df)} rows for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {e}")
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
        try:
            info = self.nse.get_quote(symbol)
            return info if info else {}
        except Exception as e:
            logger.error(f"Error fetching company info for {symbol}: {e}")
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
        try:
            logger.info(f"Fetching index data for {index}")

            # For indices, we might need to use a different approach
            # NSE package may have limitations for index historical data
            data = self.nse.get_hist(
                symbol=index,
                from_date=start_date.strftime('%d-%m-%Y'),
                to_date=end_date.strftime('%d-%m-%Y')
            )

            if data:
                df = pd.DataFrame(data)
                if 'CH_TIMESTAMP' in df.columns:
                    df['Date'] = pd.to_datetime(df['CH_TIMESTAMP'])
                    df.set_index('Date', inplace=True)
                if 'CH_CLOSING_PRICE' in df.columns:
                    df['Close'] = df['CH_CLOSING_PRICE']
                    df['Return'] = df['Close'].pct_change()
                return df

            return None

        except Exception as e:
            logger.error(f"Error fetching index data: {e}")
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
        try:
            actions = self.nse.get_corporate_actions(symbol)
            if actions:
                return pd.DataFrame(actions)
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching corporate actions for {symbol}: {e}")
            return pd.DataFrame()
