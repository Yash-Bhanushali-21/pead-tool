"""
Abnormal Returns Calculation
Computes abnormal returns: AR = R_actual - R_expected
R_expected comes from market model
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging
from datetime import datetime
from scipy import stats

from .market_model import MarketModel
from ..config.settings import config

logger = logging.getLogger(__name__)


class AbnormalReturns:
    """
    Calculate abnormal returns using market model
    AR_t = R_stock,t - (α + β * R_market,t)
    """

    def __init__(self, market_model: Optional[MarketModel] = None):
        """
        Initialize abnormal returns calculator

        Parameters
        ----------
        market_model : MarketModel, optional
            Pre-estimated market model (if None, will estimate)
        """
        self.market_model = market_model or MarketModel()
        self.abnormal_returns = None
        self.abnormal_returns_stats = None

    def calculate(
        self,
        stock_returns: pd.Series,
        market_returns: pd.Series,
        announcement_date: datetime,
        event_window: Tuple[int, int] = (0, 90),
        estimate_model: bool = True
    ) -> pd.DataFrame:
        """
        Calculate abnormal returns around announcement

        Parameters
        ----------
        stock_returns : pd.Series
            Stock returns
        market_returns : pd.Series
            Market returns
        announcement_date : datetime
            Announcement date
        event_window : tuple
            (start_day, end_day) relative to announcement
            e.g., (0, 90) for 90 days after announcement
        estimate_model : bool
            Whether to estimate market model (if not already estimated)

        Returns
        -------
        pd.DataFrame
            DataFrame with Date, AR, expected_return, actual_return
        """
        # Estimate market model if needed
        if estimate_model or self.market_model.alpha is None:
            logger.info("Estimating market model for AR calculation")
            self.market_model.estimate(
                stock_returns,
                market_returns,
                announcement_date
            )

        # Align data
        data = pd.DataFrame({
            'stock_return': stock_returns,
            'market_return': market_returns
        }).dropna()

        # Calculate expected returns using market model
        data['expected_return'] = (
            self.market_model.alpha +
            self.market_model.beta * data['market_return']
        )

        # Calculate abnormal returns
        data['AR'] = data['stock_return'] - data['expected_return']

        # Filter to event window
        event_data = self._filter_event_window(
            data,
            announcement_date,
            event_window
        )

        # Calculate statistics
        self.abnormal_returns = event_data
        self._calculate_statistics()

        logger.info(
            f"Calculated {len(event_data)} abnormal returns for event window "
            f"{event_window}"
        )

        return event_data

    def _filter_event_window(
        self,
        data: pd.DataFrame,
        announcement_date: datetime,
        window: Tuple[int, int]
    ) -> pd.DataFrame:
        """
        Filter data to event window

        Parameters
        ----------
        data : pd.DataFrame
            Full dataset
        announcement_date : datetime
            Event date
        window : tuple
            (start_offset, end_offset) in trading days

        Returns
        -------
        pd.DataFrame
            Filtered data
        """
        # Get dates after announcement
        after_announcement = data[data.index >= announcement_date].copy()

        start_offset, end_offset = window

        # Filter based on position
        if len(after_announcement) > 0:
            event_data = after_announcement.iloc[
                max(0, start_offset):min(len(after_announcement), end_offset + 1)
            ]
        else:
            event_data = pd.DataFrame()

        # Add trading day index
        if len(event_data) > 0:
            event_data['trading_day'] = range(start_offset, start_offset + len(event_data))

        return event_data

    def _calculate_statistics(self) -> None:
        """Calculate statistical properties of abnormal returns"""
        if self.abnormal_returns is None or len(self.abnormal_returns) == 0:
            return

        ar_series = self.abnormal_returns['AR']

        self.abnormal_returns_stats = {
            'mean_ar': ar_series.mean(),
            'median_ar': ar_series.median(),
            'std_ar': ar_series.std(),
            'min_ar': ar_series.min(),
            'max_ar': ar_series.max(),
            'positive_ar_count': (ar_series > 0).sum(),
            'negative_ar_count': (ar_series < 0).sum(),
            'positive_ar_pct': (ar_series > 0).sum() / len(ar_series) * 100,
        }

        # T-test for mean AR
        if len(ar_series) > 1:
            t_stat, p_value = stats.ttest_1samp(ar_series, 0)
            self.abnormal_returns_stats['t_statistic'] = t_stat
            self.abnormal_returns_stats['p_value'] = p_value
            self.abnormal_returns_stats['significant'] = p_value < config.SIGNIFICANCE_LEVEL

    def get_statistics(self) -> Dict:
        """
        Get abnormal returns statistics

        Returns
        -------
        dict
            Statistical summary
        """
        return self.abnormal_returns_stats or {}

    def test_significance(self, alpha: float = 0.05) -> Dict:
        """
        Test statistical significance of abnormal returns

        Parameters
        ----------
        alpha : float
            Significance level

        Returns
        -------
        dict
            Test results
        """
        if self.abnormal_returns is None:
            return {'error': 'No abnormal returns calculated'}

        ar_series = self.abnormal_returns['AR'].dropna()

        if len(ar_series) < 2:
            return {'error': 'Insufficient data for significance testing'}

        # One-sample t-test (H0: mean AR = 0)
        t_stat, p_value = stats.ttest_1samp(ar_series, 0)

        # Sign test (non-parametric)
        positive_count = (ar_series > 0).sum()
        n = len(ar_series)
        sign_test_p = 2 * min(
            stats.binom.cdf(positive_count, n, 0.5),
            1 - stats.binom.cdf(positive_count - 1, n, 0.5)
        )

        # Wilcoxon signed-rank test
        try:
            wilcoxon_stat, wilcoxon_p = stats.wilcoxon(ar_series)
        except Exception:
            wilcoxon_stat, wilcoxon_p = None, None

        results = {
            't_test': {
                't_statistic': t_stat,
                'p_value': p_value,
                'significant': p_value < alpha,
                'mean_ar': ar_series.mean()
            },
            'sign_test': {
                'positive_count': positive_count,
                'negative_count': n - positive_count,
                'p_value': sign_test_p,
                'significant': sign_test_p < alpha
            },
            'wilcoxon_test': {
                'statistic': wilcoxon_stat,
                'p_value': wilcoxon_p,
                'significant': wilcoxon_p < alpha if wilcoxon_p else False
            } if wilcoxon_p else None
        }

        return results

    def get_summary(self) -> str:
        """
        Get summary of abnormal returns analysis

        Returns
        -------
        str
            Summary string
        """
        if self.abnormal_returns_stats is None:
            return "No abnormal returns calculated"

        stats_dict = self.abnormal_returns_stats

        summary = f"""
Abnormal Returns Summary
========================
Mean AR:           {stats_dict['mean_ar']:>10.6f}
Median AR:         {stats_dict['median_ar']:>10.6f}
Std Dev:           {stats_dict['std_ar']:>10.6f}
Min AR:            {stats_dict['min_ar']:>10.6f}
Max AR:            {stats_dict['max_ar']:>10.6f}
Positive AR:       {stats_dict['positive_ar_count']:>10d} ({stats_dict['positive_ar_pct']:.1f}%)
Negative AR:       {stats_dict['negative_ar_count']:>10d}
"""

        if 't_statistic' in stats_dict:
            summary += f"""
T-statistic:       {stats_dict['t_statistic']:>10.4f}
P-value:           {stats_dict['p_value']:>10.6f}
Significant:       {stats_dict['significant']}
"""

        return summary

    def plot_abnormal_returns(self, save_path: Optional[str] = None):
        """
        Plot abnormal returns over time

        Parameters
        ----------
        save_path : str, optional
            Path to save plot
        """
        if self.abnormal_returns is None:
            logger.warning("No abnormal returns to plot")
            return

        import matplotlib.pyplot as plt
        import seaborn as sns

        sns.set_style("whitegrid")

        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # Plot AR over time
        ax1 = axes[0]
        self.abnormal_returns['AR'].plot(ax=ax1, color='steelblue', linewidth=1.5)
        ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5)
        ax1.set_title('Abnormal Returns Over Time', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Abnormal Return', fontsize=12)
        ax1.grid(True, alpha=0.3)

        # Plot distribution
        ax2 = axes[1]
        self.abnormal_returns['AR'].hist(bins=30, ax=ax2, color='steelblue', alpha=0.7)
        ax2.axvline(x=0, color='red', linestyle='--', alpha=0.5)
        ax2.set_title('Distribution of Abnormal Returns', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Abnormal Return', fontsize=12)
        ax2.set_ylabel('Frequency', fontsize=12)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")
        else:
            plt.show()

        plt.close()
