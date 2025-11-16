"""
Yahoo Finance Data Fetcher
Fallback/supplementary data source when NSE data is unavailable
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging
import yfinance as yf

logger = logging.getLogger(__name__)


class YahooDataFetcher:
    """Fetch data from Yahoo Finance as fallback"""

    @staticmethod
    def nse_to_yahoo_symbol(nse_symbol: str) -> str:
        """
        Convert NSE symbol to Yahoo Finance format

        Parameters
        ----------
        nse_symbol : str
            NSE symbol (e.g., 'RELIANCE')

        Returns
        -------
        str
            Yahoo Finance symbol (e.g., 'RELIANCE.NS')
        """
        # NSE stocks have .NS suffix, BSE have .BO
        if not nse_symbol.endswith('.NS') and not nse_symbol.endswith('.BO'):
            return f"{nse_symbol}.NS"
        return nse_symbol

    def get_stock_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Get historical stock data from Yahoo Finance

        Parameters
        ----------
        symbol : str
            NSE stock symbol
        start_date : datetime
            Start date
        end_date : datetime
            End date

        Returns
        -------
        pd.DataFrame or None
            Stock data with OHLCV
        """
        try:
            yahoo_symbol = self.nse_to_yahoo_symbol(symbol)
            logger.info(f"Fetching Yahoo data for {yahoo_symbol}")

            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(start=start_date, end=end_date)

            if df.empty:
                logger.warning(f"No Yahoo data for {yahoo_symbol}")
                return None

            # Calculate returns
            df['Return'] = df['Close'].pct_change()

            # Ensure date index
            df.index.name = 'Date'

            logger.info(f"Fetched {len(df)} rows from Yahoo for {yahoo_symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching Yahoo data for {symbol}: {e}")
            return None

    def get_index_data(
        self,
        index_symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Get index data from Yahoo Finance

        Parameters
        ----------
        index_symbol : str
            Index symbol (e.g., '^NSEI' for NIFTY 50)
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
            logger.info(f"Fetching Yahoo index data for {index_symbol}")

            ticker = yf.Ticker(index_symbol)
            df = ticker.history(start=start_date, end=end_date)

            if df.empty:
                logger.warning(f"No Yahoo data for index {index_symbol}")
                return None

            # Calculate returns
            df['Return'] = df['Close'].pct_change()
            df.index.name = 'Date'

            logger.info(f"Fetched {len(df)} index rows from Yahoo")
            return df

        except Exception as e:
            logger.error(f"Error fetching Yahoo index data: {e}")
            return None

    def get_company_info(self, symbol: str) -> Dict:
        """
        Get company information from Yahoo Finance

        Parameters
        ----------
        symbol : str
            NSE symbol

        Returns
        -------
        dict
            Company information
        """
        try:
            yahoo_symbol = self.nse_to_yahoo_symbol(symbol)
            ticker = yf.Ticker(yahoo_symbol)
            info = ticker.info

            # Extract relevant financial metrics
            return {
                'symbol': symbol,
                'company_name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', None),
                'eps': info.get('trailingEps', None),
                'dividend_yield': info.get('dividendYield', None),
                'beta': info.get('beta', None),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh', None),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow', None),
            }

        except Exception as e:
            logger.error(f"Error fetching Yahoo company info for {symbol}: {e}")
            return {}

    def get_financials(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """
        Get financial statements from Yahoo Finance

        Parameters
        ----------
        symbol : str
            NSE symbol

        Returns
        -------
        dict
            Dictionary containing income statement, balance sheet, cash flow
        """
        try:
            yahoo_symbol = self.nse_to_yahoo_symbol(symbol)
            ticker = yf.Ticker(yahoo_symbol)

            financials = {
                'income_statement': ticker.financials,
                'balance_sheet': ticker.balance_sheet,
                'cash_flow': ticker.cashflow,
                'quarterly_financials': ticker.quarterly_financials,
            }

            logger.info(f"Fetched financials for {yahoo_symbol}")
            return financials

        except Exception as e:
            logger.error(f"Error fetching financials for {symbol}: {e}")
            return {}

    def get_earnings_dates(self, symbol: str) -> pd.DataFrame:
        """
        Get earnings dates from Yahoo Finance

        Parameters
        ----------
        symbol : str
            NSE symbol

        Returns
        -------
        pd.DataFrame
            Earnings dates and estimates
        """
        try:
            yahoo_symbol = self.nse_to_yahoo_symbol(symbol)
            ticker = yf.Ticker(yahoo_symbol)
            earnings = ticker.earnings_dates

            if earnings is not None and not earnings.empty:
                return earnings

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching earnings dates for {symbol}: {e}")
            return pd.DataFrame()
