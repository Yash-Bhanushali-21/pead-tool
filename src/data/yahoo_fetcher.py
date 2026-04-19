"""
Yahoo Finance data fetcher using `yfinance` (https://github.com/ranaroussi/yfinance ).

Fallback when NSE (nsepython) is unavailable. Yahoo terms apply; library is unaffiliated with Yahoo.
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple
import logging
import yfinance as yf

from src.utils.time_compat import to_calendar_date

logger = logging.getLogger(__name__)

# If a start/end ``history()`` call returns bars whose first session is this many calendar
# days after ``start_d``, yfinance often served a *tail-only* slice — retry ``period="max"``.
_YAHOO_TAIL_ONLY_SLACK_DAYS = 14


class YahooDataFetcher:
    """Fetch data from Yahoo Finance as fallback"""

    @staticmethod
    def _squash_multilevel_columns(df: pd.DataFrame) -> pd.DataFrame:
        """yfinance 0.2+ may return columns like ``(Open, TICKER.NS)``."""
        if not isinstance(df.columns, pd.MultiIndex):
            return df
        out = df.copy()
        out.columns = [str(c[0]) for c in out.columns]
        return out

    @staticmethod
    def _calendar_first_index_day(df: Optional[pd.DataFrame]) -> Optional[pd.Timestamp]:
        if df is None or df.empty:
            return None
        idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True)).tz_convert(None).normalize()
        return pd.Timestamp(to_calendar_date(idx.min()))

    @staticmethod
    def _clip_to_calendar_range(df: pd.DataFrame, start_d: date, end_d: date) -> pd.DataFrame:
        """Inclusive calendar clip; index normalized to naive midnight."""
        if df.empty:
            return df
        work = df.copy()
        idx = pd.DatetimeIndex(pd.to_datetime(work.index, utc=True)).tz_convert(None).normalize()
        work.index = idx
        lo = pd.Timestamp(to_calendar_date(start_d))
        hi = pd.Timestamp(to_calendar_date(end_d))
        return work.loc[(work.index >= lo) & (work.index <= hi)].copy()

    @staticmethod
    def _yahoo_tail_only_slice(df: pd.DataFrame, want_start: date) -> bool:
        if df is None or df.empty:
            return False
        first = YahooDataFetcher._calendar_first_index_day(df)
        if first is None:
            return False
        return bool(first > pd.Timestamp(want_start) + timedelta(days=_YAHOO_TAIL_ONLY_SLACK_DAYS))

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
            # yfinance accepts datetime.date; avoid passing datetimes that confuse strict builds.
            start_d = to_calendar_date(start_date)
            end_d = to_calendar_date(end_date)
            end_exclusive = end_d + timedelta(days=1)
            df = ticker.history(start=start_d, end=end_exclusive, auto_adjust=True, actions=False)
            df = self._squash_multilevel_columns(df)

            if df.empty:
                logger.warning(f"No Yahoo data for {yahoo_symbol}")
                return None
            if "Close" not in df.columns:
                logger.warning("Yahoo response for %s has no Close column after normalize", yahoo_symbol)
                return None

            if self._yahoo_tail_only_slice(df, start_d):
                logger.warning(
                    "Yahoo range query for %s is tail-only (first bar %s vs requested %s); "
                    "retrying period=max and clipping to window",
                    yahoo_symbol,
                    self._calendar_first_index_day(df),
                    start_d,
                )
                df_max = ticker.history(period="max", auto_adjust=True, actions=False)
                df_max = self._squash_multilevel_columns(df_max)
                if df_max is not None and not df_max.empty:
                    clipped = self._clip_to_calendar_range(df_max, start_d, end_d)
                    first_range = self._calendar_first_index_day(df)
                    first_clip = self._calendar_first_index_day(clipped)
                    if (
                        not clipped.empty
                        and first_clip is not None
                        and (first_range is None or first_clip < first_range or len(clipped) > len(df))
                    ):
                        df = clipped
                        logger.info(
                            "Yahoo period=max repaired history for %s (%d rows in window)",
                            yahoo_symbol,
                            len(df),
                        )

            # Calculate returns
            df["Return"] = df["Close"].pct_change()

            # Ensure date index
            df.index.name = "Date"

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
            start_d = to_calendar_date(start_date)
            end_d = to_calendar_date(end_date)
            end_exclusive = end_d + timedelta(days=1)
            df = ticker.history(start=start_d, end=end_exclusive, auto_adjust=True, actions=False)
            df = self._squash_multilevel_columns(df)

            if df.empty:
                logger.warning(f"No Yahoo data for index {index_symbol}")
                return None
            if "Close" not in df.columns:
                logger.warning("Yahoo index response for %s has no Close after normalize", index_symbol)
                return None

            if self._yahoo_tail_only_slice(df, start_d):
                logger.warning(
                    "Yahoo range query for index %s is tail-only (first bar %s vs requested %s); "
                    "retrying period=max",
                    index_symbol,
                    self._calendar_first_index_day(df),
                    start_d,
                )
                df_max = ticker.history(period="max", auto_adjust=True, actions=False)
                df_max = self._squash_multilevel_columns(df_max)
                if df_max is not None and not df_max.empty:
                    clipped = self._clip_to_calendar_range(df_max, start_d, end_d)
                    first_range = self._calendar_first_index_day(df)
                    first_clip = self._calendar_first_index_day(clipped)
                    if (
                        not clipped.empty
                        and first_clip is not None
                        and (first_range is None or first_clip < first_range or len(clipped) > len(df))
                    ):
                        df = clipped
                        logger.info(
                            "Yahoo period=max repaired index history for %s (%d rows in window)",
                            index_symbol,
                            len(df),
                        )

            df["Return"] = df["Close"].pct_change()
            df.index.name = "Date"

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

    def get_yoy_quarter_metrics(self, symbol: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Latest quarter vs year-ago quarter (same fiscal seasonality) from Yahoo statements.

        Used when announcement PDFs are missing so earnings-surprise scoring is not stuck at zero.
        Maps net-income growth into the same `eps` slot used by EarningsSurpriseScorer (earnings growth).
        """
        empty: Tuple[Dict[str, Any], Dict[str, Any]] = ({}, {})
        try:
            yahoo_symbol = self.nse_to_yahoo_symbol(symbol)
            ticker = yf.Ticker(yahoo_symbol)
            inc = getattr(ticker, "quarterly_income_stmt", None)
            if inc is None or not isinstance(inc, pd.DataFrame) or inc.empty or inc.shape[1] < 5:
                inc = ticker.quarterly_financials
            if inc is None or not isinstance(inc, pd.DataFrame) or inc.empty or inc.shape[1] < 5:
                return empty

            dates = sorted(inc.columns, reverse=True)
            d0, d4 = dates[0], dates[4]

            def _pick_row(names: Tuple[str, ...]) -> Optional[str]:
                for n in names:
                    if n in inc.index:
                        return n
                return None

            rev_row = _pick_row(("Total Revenue", "Total Revenues", "Operating Revenue"))
            ni_row = _pick_row(("Net Income", "Net Income Common Stockholders"))
            op_row = _pick_row(("Operating Income", "Operating Income Loss"))

            current: Dict[str, Any] = {}
            yoy: Dict[str, Any] = {}

            if rev_row:
                r0, r4 = inc.loc[rev_row, d0], inc.loc[rev_row, d4]
                if pd.notna(r0) and pd.notna(r4):
                    current["revenue"] = float(r0)
                    yoy["revenue"] = float(r4)

            if ni_row:
                n0, n4 = inc.loc[ni_row, d0], inc.loc[ni_row, d4]
                if pd.notna(n0) and pd.notna(n4):
                    # Scorer interprets as EPS-style growth; we use net income YoY as scale-free earnings proxy
                    current["eps"] = float(n0)
                    yoy["eps"] = float(n4)

            if op_row and rev_row:
                r0 = inc.loc[rev_row, d0]
                o0 = inc.loc[op_row, d0]
                r4 = inc.loc[rev_row, d4]
                o4 = inc.loc[op_row, d4]
                if pd.notna(r0) and pd.notna(o0) and float(r0) != 0:
                    current["operating_margin"] = float(o0) / float(r0) * 100.0
                if pd.notna(r4) and pd.notna(o4) and float(r4) != 0:
                    yoy["operating_margin"] = float(o4) / float(r4) * 100.0

            if not current or not yoy:
                return empty

            logger.info(f"YoY quarter metrics from Yahoo for {yahoo_symbol} (vs year-ago quarter)")
            return current, yoy

        except Exception as e:
            logger.warning(f"YoY quarter metrics unavailable for {symbol}: {e}")
            return empty

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
