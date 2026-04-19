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
    """Fetch data from Yahoo Finance as fallback."""

    SOURCE_ID = "yahoo"

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
        # Yahoo index / futures tickers use caret or vendor-specific roots — do not append .NS
        if nse_symbol.startswith("^"):
            return nse_symbol
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
            # yfinance accepts datetime.date; avoid passing datetimes that confuse strict builds.
            start_d = to_calendar_date(start_date)
            end_d = to_calendar_date(end_date)
            end_exclusive = end_d + timedelta(days=1)
            logger.info(
                "data_fetch source=yahoo kind=equity_ohlcv input_symbol=%s yahoo_symbol=%s "
                "api=yfinance.Ticker.history start=%s end=%s (yfinance end is exclusive; "
                "passing end=%s) auto_adjust=True actions=False",
                symbol,
                yahoo_symbol,
                start_d,
                end_exclusive,
                end_d,
            )

            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(start=start_d, end=end_exclusive, auto_adjust=True, actions=False)
            df = self._squash_multilevel_columns(df)

            if df.empty:
                logger.warning(
                    "data_fetch source=yahoo kind=equity_ohlcv yahoo_symbol=%s result=empty "
                    "requested_start=%s requested_end_inclusive=%s",
                    yahoo_symbol,
                    start_d,
                    end_d,
                )
                return None
            if "Close" not in df.columns:
                logger.warning(
                    "data_fetch source=yahoo kind=equity_ohlcv yahoo_symbol=%s result=invalid "
                    "reason=no_close_column",
                    yahoo_symbol,
                )
                return None

            if self._yahoo_tail_only_slice(df, start_d):
                logger.warning(
                    "data_fetch source=yahoo kind=equity_ohlcv yahoo_symbol=%s repair=period_max "
                    "reason=tail_only_slice first_bar=%s requested_start=%s",
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
                            "data_fetch source=yahoo kind=equity_ohlcv yahoo_symbol=%s "
                            "repair=period_max result=applied rows_in_window=%d",
                            yahoo_symbol,
                            len(df),
                        )

            # Calculate returns
            df["Return"] = df["Close"].pct_change()

            # Ensure date index
            df.index.name = "Date"

            idx = df.index
            logger.info(
                "data_fetch source=yahoo kind=equity_ohlcv yahoo_symbol=%s result=ok rows=%d "
                "bar_first=%s bar_last=%s",
                yahoo_symbol,
                len(df),
                pd.Timestamp(idx.min()).date().isoformat() if len(idx) else None,
                pd.Timestamp(idx.max()).date().isoformat() if len(idx) else None,
            )
            return df

        except Exception as e:
            logger.error(
                "data_fetch source=yahoo kind=equity_ohlcv input_symbol=%s error=%s",
                symbol,
                e,
                exc_info=True,
            )
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
            start_d = to_calendar_date(start_date)
            end_d = to_calendar_date(end_date)
            end_exclusive = end_d + timedelta(days=1)
            logger.info(
                "data_fetch source=yahoo kind=index_ohlcv yahoo_symbol=%s "
                "api=yfinance.Ticker.history start=%s end=%s (yfinance end exclusive; inclusive_end=%s) "
                "auto_adjust=True actions=False",
                index_symbol,
                start_d,
                end_exclusive,
                end_d,
            )

            ticker = yf.Ticker(index_symbol)
            df = ticker.history(start=start_d, end=end_exclusive, auto_adjust=True, actions=False)
            df = self._squash_multilevel_columns(df)

            if df.empty:
                logger.warning(
                    "data_fetch source=yahoo kind=index_ohlcv yahoo_symbol=%s result=empty "
                    "requested_start=%s requested_end_inclusive=%s",
                    index_symbol,
                    start_d,
                    end_d,
                )
                return None
            if "Close" not in df.columns:
                logger.warning(
                    "data_fetch source=yahoo kind=index_ohlcv yahoo_symbol=%s result=invalid "
                    "reason=no_close_column",
                    index_symbol,
                )
                return None

            if self._yahoo_tail_only_slice(df, start_d):
                logger.warning(
                    "data_fetch source=yahoo kind=index_ohlcv yahoo_symbol=%s repair=period_max "
                    "reason=tail_only_slice first_bar=%s requested_start=%s",
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
                            "data_fetch source=yahoo kind=index_ohlcv yahoo_symbol=%s "
                            "repair=period_max result=applied rows_in_window=%d",
                            index_symbol,
                            len(df),
                        )

            df["Return"] = df["Close"].pct_change()
            df.index.name = "Date"

            idx = df.index
            logger.info(
                "data_fetch source=yahoo kind=index_ohlcv yahoo_symbol=%s result=ok rows=%d "
                "bar_first=%s bar_last=%s",
                index_symbol,
                len(df),
                pd.Timestamp(idx.min()).date().isoformat() if len(idx) else None,
                pd.Timestamp(idx.max()).date().isoformat() if len(idx) else None,
            )
            return df

        except Exception as e:
            logger.error(
                "data_fetch source=yahoo kind=index_ohlcv yahoo_symbol=%s error=%s",
                index_symbol,
                e,
                exc_info=True,
            )
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
            logger.info(
                "data_fetch source=yahoo kind=company_info input_symbol=%s yahoo_symbol=%s "
                "api=yfinance.Ticker.info",
                symbol,
                yahoo_symbol,
            )
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
            logger.error(
                "data_fetch source=yahoo kind=company_info input_symbol=%s error=%s",
                symbol,
                e,
                exc_info=True,
            )
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
            logger.info(
                "data_fetch source=yahoo kind=financials input_symbol=%s yahoo_symbol=%s "
                "api=yfinance (financials balance_sheet cashflow quarterly_financials)",
                symbol,
                yahoo_symbol,
            )
            ticker = yf.Ticker(yahoo_symbol)

            financials = {
                'income_statement': ticker.financials,
                'balance_sheet': ticker.balance_sheet,
                'cash_flow': ticker.cashflow,
                'quarterly_financials': ticker.quarterly_financials,
            }

            logger.info(
                "data_fetch source=yahoo kind=financials yahoo_symbol=%s result=ok",
                yahoo_symbol,
            )
            return financials

        except Exception as e:
            logger.error(
                "data_fetch source=yahoo kind=financials input_symbol=%s error=%s",
                symbol,
                e,
                exc_info=True,
            )
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
            logger.info(
                "data_fetch source=yahoo kind=yoy_quarter_metrics input_symbol=%s yahoo_symbol=%s "
                "api=yfinance quarterly_income_stmt|quarterly_financials",
                symbol,
                yahoo_symbol,
            )
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

            logger.info(
                "data_fetch source=yahoo kind=yoy_quarter_metrics yahoo_symbol=%s result=ok",
                yahoo_symbol,
            )
            return current, yoy

        except Exception as e:
            logger.warning(
                "data_fetch source=yahoo kind=yoy_quarter_metrics input_symbol=%s error=%s",
                symbol,
                e,
                exc_info=True,
            )
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
            logger.info(
                "data_fetch source=yahoo kind=earnings_dates input_symbol=%s yahoo_symbol=%s "
                "api=yfinance.Ticker.earnings_dates",
                symbol,
                yahoo_symbol,
            )
            ticker = yf.Ticker(yahoo_symbol)
            earnings = ticker.earnings_dates

            if earnings is not None and not earnings.empty:
                logger.info(
                    "data_fetch source=yahoo kind=earnings_dates yahoo_symbol=%s result=ok rows=%d",
                    yahoo_symbol,
                    len(earnings),
                )
                return earnings

            logger.info(
                "data_fetch source=yahoo kind=earnings_dates yahoo_symbol=%s result=empty",
                yahoo_symbol,
            )
            return pd.DataFrame()

        except Exception as e:
            logger.error(
                "data_fetch source=yahoo kind=earnings_dates input_symbol=%s error=%s",
                symbol,
                e,
                exc_info=True,
            )
            return pd.DataFrame()
