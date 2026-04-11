"""
Cumulative Abnormal Returns (CAR)
Computes CAR over various windows for PEAD analysis
CAR(t1, t2) = Σ AR_t for t in [t1, t2]
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from scipy import stats

from src.models.abnormal_returns import AbnormalReturns
from src.config.config import config

logger = logging.getLogger(__name__)


class CumulativeAbnormalReturns:
    """
    Calculate CAR for multiple windows
    Standard windows: [1, 10, 30, 60, 90] days post-announcement
    """

    def __init__(self, abnormal_returns: Optional[AbnormalReturns] = None):
        """
        Initialize CAR calculator

        Parameters
        ----------
        abnormal_returns : AbnormalReturns, optional
            Pre-calculated abnormal returns
        """
        self.ar_calculator = abnormal_returns or AbnormalReturns()
        self.cars = {}
        self.car_statistics = {}

    def calculate(
        self,
        ar_data: pd.DataFrame,
        windows: Optional[List[int]] = None,
        estimation_residual_std: Optional[float] = None,
        estimation_t_df: Optional[int] = None,
    ) -> Dict[int, Dict]:
        """
        Calculate CAR for multiple windows

        Parameters
        ----------
        ar_data : pd.DataFrame
            DataFrame with abnormal returns (must have 'AR' column)
        windows : list of int, optional
            List of window lengths in trading days

        Returns
        -------
        dict
            CAR values and statistics for each window
        """
        if windows is None:
            windows = config.CAR_WINDOWS

        # Check if data is empty
        if ar_data is None or len(ar_data) == 0:
            logger.warning("No abnormal returns data available for CAR calculation")
            # Return empty dict with zero CARs
            for window in windows:
                self.cars[window] = {
                    'window': window,
                    'car': 0,
                    'car_pct': 0,
                    'actual_days': 0,
                    'mean_daily_ar': 0,
                    'std_daily_ar': 0,
                    't_statistic': 0,
                    'p_value': 1.0,
                    'significant': False,
                    'annualized_return': 0,
                    'car_test_uses_estimation_sigma': False,
                }
            return self.cars

        if 'AR' not in ar_data.columns:
            raise ValueError("Input data must have 'AR' column")

        logger.info(f"Calculating CAR for windows: {windows}")

        for window in windows:
            self.cars[window] = self._calculate_window_car(
                ar_data,
                window,
                estimation_residual_std=estimation_residual_std,
                estimation_t_df=estimation_t_df,
            )

        return self.cars

    def _calculate_window_car(
        self,
        ar_data: pd.DataFrame,
        window: int,
        estimation_residual_std: Optional[float] = None,
        estimation_t_df: Optional[int] = None,
    ) -> Dict:
        """
        Calculate CAR for a specific window

        Parameters
        ----------
        ar_data : pd.DataFrame
            Abnormal returns data
        window : int
            Window length (trading days from announcement)

        Returns
        -------
        dict
            CAR value and statistics for this window
        """
        # Get AR values for this window
        ar_window = ar_data.head(window)

        if len(ar_window) == 0:
            logger.warning(f"No data for window {window}")
            return {
                'window': window,
                'car': 0,
                'car_pct': 0,
                'actual_days': 0,
                'mean_daily_ar': 0,
                'std_daily_ar': 0,
                't_statistic': 0,
                'p_value': 1.0,
                'significant': False,
                'car_test_uses_estimation_sigma': False,
            }

        # Calculate CAR (sum of ARs)
        car_value = ar_window['AR'].sum()
        actual_days = len(ar_window)
        mean_daily_ar = ar_window['AR'].mean()
        std_daily_ar = ar_window['AR'].std(ddof=1) if actual_days > 1 else 0.0

        # Significance: prefer estimation-window residual σ (event-study standard).
        # Under i.i.d. residual assumption: Var(CAR_{0,L}) ≈ L * σ²_ε (Patell 1976; MacKinlay 1997).
        uses_est_sigma = (
            estimation_residual_std is not None
            and np.isfinite(estimation_residual_std)
            and estimation_residual_std > 0
        )
        if uses_est_sigma:
            sigma = float(estimation_residual_std)
            se_car = sigma * np.sqrt(actual_days)
            t_stat = car_value / se_car if se_car > 0 else 0.0
            df = estimation_t_df if estimation_t_df is not None and estimation_t_df > 0 else max(actual_days - 1, 1)
        elif (
            np.isfinite(std_daily_ar)
            and std_daily_ar > 0
            and actual_days > 1
        ):
            # Fallback: in-window sample std (biased for single-name tests; flagged in output)
            se_car = std_daily_ar * np.sqrt(actual_days)
            t_stat = car_value / se_car
            df = actual_days - 1
        else:
            t_stat = 0.0
            df = 1
            p_value = 1.0
            significant = False
            result = {
                'window': window,
                'car': car_value,
                'car_pct': car_value * 100,
                'actual_days': actual_days,
                'mean_daily_ar': mean_daily_ar,
                'std_daily_ar': std_daily_ar,
                't_statistic': t_stat,
                'p_value': p_value,
                'significant': significant,
                'annualized_return': self._annualize_car(car_value, actual_days),
                'car_test_uses_estimation_sigma': uses_est_sigma,
            }
            return result

        p_value = float(2 * (1 - stats.t.cdf(abs(t_stat), df)))
        significant = p_value < config.SIGNIFICANCE_LEVEL

        result = {
            'window': window,
            'car': car_value,
            # Human-readable percent number (e.g. 3.27 means 3.27%); use `car` for decimal (0.0327)
            'car_pct': car_value * 100,
            'actual_days': actual_days,
            'mean_daily_ar': mean_daily_ar,
            'std_daily_ar': std_daily_ar,
            't_statistic': t_stat,
            'p_value': p_value,
            'significant': significant,
            'annualized_return': self._annualize_car(car_value, actual_days),
            'car_test_uses_estimation_sigma': uses_est_sigma,
        }

        logger.info(
            f"CAR({window}): {car_value:.6f} ({car_value*100:.2f}%), "
            f"t={t_stat:.2f}, p={p_value:.4f}, sig={significant}"
        )

        return result

    def _annualize_car(self, car: float, days: int) -> float:
        """
        Annualize CAR for comparison

        Parameters
        ----------
        car : float
            Cumulative abnormal return
        days : int
            Number of trading days

        Returns
        -------
        float
            Annualized return
        """
        if days <= 0:
            return 0

        trading_days_per_year = 252
        annualized = ((1 + car) ** (trading_days_per_year / days) - 1)
        return annualized

    def get_car(self, window: int) -> Optional[float]:
        """
        Get CAR value for specific window

        Parameters
        ----------
        window : int
            Window length

        Returns
        -------
        float or None
            CAR value
        """
        if window in self.cars:
            return self.cars[window]['car']
        return None

    def get_all_cars(self) -> Dict[int, float]:
        """
        Get all CAR values

        Returns
        -------
        dict
            Mapping of window to CAR value
        """
        return {w: self.cars[w]['car'] for w in self.cars}

    def get_significant_windows(self) -> List[int]:
        """
        Get windows with statistically significant CARs

        Returns
        -------
        list
            Windows with significant drift
        """
        return [
            window for window, data in self.cars.items()
            if data.get('significant', False)
        ]

    def calculate_drift_persistence(self) -> Dict:
        """
        Analyze how CAR evolves across windows (persistence of drift)

        Returns
        -------
        dict
            Drift persistence metrics
        """
        if not self.cars:
            return {}

        sorted_windows = sorted(self.cars.keys())
        car_values = [self.cars[w]['car'] for w in sorted_windows]

        # Check for monotonic increase (strong persistence)
        is_monotonic = all(
            car_values[i] <= car_values[i+1]
            for i in range(len(car_values) - 1)
        )

        # Peak CAR window
        max_car_window = max(self.cars.items(), key=lambda x: abs(x[1]['car']))[0]

        # Early vs late drift
        early_windows = [w for w in sorted_windows if w <= 10]
        late_windows = [w for w in sorted_windows if w > 30]

        early_car_avg = np.mean([self.cars[w]['car'] for w in early_windows]) if early_windows else 0
        late_car_avg = np.mean([self.cars[w]['car'] for w in late_windows]) if late_windows else 0

        persistence = {
            'is_monotonic': is_monotonic,
            'peak_car_window': max_car_window,
            'peak_car_value': self.cars[max_car_window]['car'],
            'early_drift_avg': early_car_avg,
            'late_drift_avg': late_car_avg,
            'drift_acceleration': late_car_avg - early_car_avg,
            'consistency_score': self._calculate_consistency_score()
        }

        return persistence

    def _calculate_consistency_score(self) -> float:
        """
        Calculate how consistent the drift is

        Returns
        -------
        float
            Consistency score (0-1, higher is more consistent)
        """
        if len(self.cars) < 2:
            return 0

        # Get sign of CARs
        car_signs = [np.sign(self.cars[w]['car']) for w in sorted(self.cars.keys())]

        # Consistency = fraction of windows with same sign as majority
        if not car_signs:
            return 0

        majority_sign = max(set(car_signs), key=car_signs.count)
        consistency = car_signs.count(majority_sign) / len(car_signs)

        return consistency

    def get_summary(self) -> str:
        """
        Get summary of CAR analysis

        Returns
        -------
        str
            Summary string
        """
        if not self.cars:
            return "No CARs calculated"

        sorted_windows = sorted(self.cars.keys())

        summary = "\nCumulative Abnormal Returns (CAR) Summary\n"
        summary += "=" * 60 + "\n"
        summary += f"{'Window':>8} {'CAR':>12} {'CAR %':>10} {'T-stat':>10} {'P-value':>10} {'Sig':>5}\n"
        summary += "-" * 60 + "\n"

        for window in sorted_windows:
            data = self.cars[window]
            summary += (
                f"{window:>8} "
                f"{data['car']:>12.6f} "
                f"{data['car_pct']:>9.2f}% "
                f"{data['t_statistic']:>10.2f} "
                f"{data['p_value']:>10.4f} "
                f"{'Yes' if data['significant'] else 'No':>5}\n"
            )

        # Add drift persistence info
        persistence = self.calculate_drift_persistence()
        summary += "\nDrift Persistence Analysis\n"
        summary += "-" * 60 + "\n"
        summary += f"Peak CAR Window:     {persistence['peak_car_window']} days\n"
        summary += f"Peak CAR Value:      {persistence['peak_car_value']:.6f}\n"
        summary += f"Monotonic Drift:     {persistence['is_monotonic']}\n"
        summary += f"Consistency Score:   {persistence['consistency_score']:.2f}\n"

        return summary

    def plot_car_evolution(self, save_path: Optional[str] = None):
        """
        Plot CAR evolution across windows

        Parameters
        ----------
        save_path : str, optional
            Path to save plot
        """
        if not self.cars:
            logger.warning("No CARs to plot")
            return

        import matplotlib.pyplot as plt
        import seaborn as sns

        sns.set_style("whitegrid")

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Plot 1: CAR values by window
        ax1 = axes[0, 0]
        windows = sorted(self.cars.keys())
        car_values = [self.cars[w]['car'] * 100 for w in windows]

        ax1.bar(windows, car_values, color='steelblue', alpha=0.7)
        ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5)
        ax1.set_xlabel('Window (days)', fontsize=12)
        ax1.set_ylabel('CAR (%)', fontsize=12)
        ax1.set_title('CAR by Window', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        # Plot 2: Significance
        ax2 = axes[0, 1]
        t_stats = [self.cars[w]['t_statistic'] for w in windows]
        colors = ['green' if self.cars[w]['significant'] else 'gray' for w in windows]

        ax2.bar(windows, t_stats, color=colors, alpha=0.7)
        ax2.axhline(y=1.96, color='red', linestyle='--', alpha=0.5, label='5% significance')
        ax2.axhline(y=-1.96, color='red', linestyle='--', alpha=0.5)
        ax2.set_xlabel('Window (days)', fontsize=12)
        ax2.set_ylabel('T-statistic', fontsize=12)
        ax2.set_title('Statistical Significance', fontsize=14, fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Plot 3: CAR evolution (line plot)
        ax3 = axes[1, 0]
        ax3.plot(windows, car_values, marker='o', linewidth=2, markersize=8, color='steelblue')
        ax3.axhline(y=0, color='red', linestyle='--', alpha=0.5)
        ax3.set_xlabel('Window (days)', fontsize=12)
        ax3.set_ylabel('CAR (%)', fontsize=12)
        ax3.set_title('CAR Evolution', fontsize=14, fontweight='bold')
        ax3.grid(True, alpha=0.3)

        # Plot 4: Daily average AR by window
        ax4 = axes[1, 1]
        avg_daily_ar = [self.cars[w]['mean_daily_ar'] * 100 for w in windows]

        ax4.bar(windows, avg_daily_ar, color='coral', alpha=0.7)
        ax4.axhline(y=0, color='red', linestyle='--', alpha=0.5)
        ax4.set_xlabel('Window (days)', fontsize=12)
        ax4.set_ylabel('Average Daily AR (%)', fontsize=12)
        ax4.set_title('Average Daily Abnormal Return', fontsize=14, fontweight='bold')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")
        else:
            plt.show()

        plt.close()

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert CAR results to DataFrame

        Returns
        -------
        pd.DataFrame
            CAR results as DataFrame
        """
        if not self.cars:
            return pd.DataFrame()

        return pd.DataFrame.from_dict(self.cars, orient='index')
