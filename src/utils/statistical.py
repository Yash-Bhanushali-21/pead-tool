"""
Statistical utilities for PEAD analysis
"""
import numpy as np
import pandas as pd
from scipy import stats
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class StatisticalUtils:
    """Statistical utility functions"""

    @staticmethod
    def calculate_sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.06
    ) -> float:
        """
        Calculate annualized Sharpe ratio

        Parameters
        ----------
        returns : pd.Series
            Daily returns
        risk_free_rate : float
            Annual risk-free rate (default 6% for India)

        Returns
        -------
        float
            Sharpe ratio
        """
        if len(returns) < 2:
            return 0

        excess_returns = returns - (risk_free_rate / 252)
        sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252)
        return sharpe

    @staticmethod
    def calculate_information_ratio(
        returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> float:
        """
        Calculate information ratio (excess return / tracking error)

        Parameters
        ----------
        returns : pd.Series
            Strategy returns
        benchmark_returns : pd.Series
            Benchmark returns

        Returns
        -------
        float
            Information ratio
        """
        # Align dates
        aligned = pd.DataFrame({
            'strategy': returns,
            'benchmark': benchmark_returns
        }).dropna()

        if len(aligned) < 2:
            return 0

        excess = aligned['strategy'] - aligned['benchmark']
        ir = (excess.mean() / excess.std()) * np.sqrt(252)
        return ir

    @staticmethod
    def bootstrap_confidence_interval(
        data: np.ndarray,
        n_iterations: int = 1000,
        confidence_level: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate bootstrap confidence interval

        Parameters
        ----------
        data : np.ndarray
            Data array
        n_iterations : int
            Number of bootstrap iterations
        confidence_level : float
            Confidence level

        Returns
        -------
        tuple
            (lower_bound, upper_bound)
        """
        means = []

        for _ in range(n_iterations):
            sample = np.random.choice(data, size=len(data), replace=True)
            means.append(np.mean(sample))

        alpha = 1 - confidence_level
        lower = np.percentile(means, alpha/2 * 100)
        upper = np.percentile(means, (1 - alpha/2) * 100)

        return lower, upper

    @staticmethod
    def test_normality(data: pd.Series) -> Dict:
        """
        Test if data is normally distributed

        Parameters
        ----------
        data : pd.Series
            Data to test

        Returns
        -------
        dict
            Test results
        """
        # Shapiro-Wilk test
        try:
            shapiro_stat, shapiro_p = stats.shapiro(data.dropna())
        except:
            shapiro_stat, shapiro_p = None, None

        # Jarque-Bera test
        try:
            jb_stat, jb_p = stats.jarque_bera(data.dropna())
        except:
            jb_stat, jb_p = None, None

        # Skewness and kurtosis
        skewness = stats.skew(data.dropna())
        kurtosis = stats.kurtosis(data.dropna())

        return {
            'shapiro_statistic': shapiro_stat,
            'shapiro_p_value': shapiro_p,
            'jarque_bera_statistic': jb_stat,
            'jarque_bera_p_value': jb_p,
            'skewness': skewness,
            'kurtosis': kurtosis,
            'is_normal': shapiro_p > 0.05 if shapiro_p else False
        }

    @staticmethod
    def calculate_var(
        returns: pd.Series,
        confidence_level: float = 0.95
    ) -> float:
        """
        Calculate Value at Risk

        Parameters
        ----------
        returns : pd.Series
            Returns data
        confidence_level : float
            Confidence level

        Returns
        -------
        float
            VaR value
        """
        var = np.percentile(returns.dropna(), (1 - confidence_level) * 100)
        return var

    @staticmethod
    def calculate_max_drawdown(cumulative_returns: pd.Series) -> Dict:
        """
        Calculate maximum drawdown

        Parameters
        ----------
        cumulative_returns : pd.Series
            Cumulative returns

        Returns
        -------
        dict
            Drawdown statistics
        """
        cumulative = (1 + cumulative_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        max_dd = drawdown.min()
        max_dd_date = drawdown.idxmin()

        return {
            'max_drawdown': max_dd,
            'max_drawdown_date': max_dd_date,
            'drawdown_series': drawdown
        }

    @staticmethod
    def autocorrelation(data: pd.Series, lags: int = 10) -> pd.Series:
        """
        Calculate autocorrelation

        Parameters
        ----------
        data : pd.Series
            Time series data
        lags : int
            Number of lags

        Returns
        -------
        pd.Series
            Autocorrelation values
        """
        from pandas.plotting import autocorrelation_plot

        acf_values = pd.Series(
            [data.autocorr(lag=i) for i in range(1, lags+1)],
            index=range(1, lags+1)
        )

        return acf_values
