"""
Market Model Estimation
Estimates alpha and beta using OLS regression on pre-announcement window
Standard approach in event study methodology
"""
import pandas as pd
import numpy as np
from scipy import stats
from typing import Tuple, Dict, Optional
import logging
from datetime import datetime

from src.config.config import config

logger = logging.getLogger(__name__)


class MarketModel:
    """
    Market model: R_stock = α + β * R_market + ε

    Estimates parameters using OLS regression on estimation window
    (typically 120 trading days before announcement)
    """

    def __init__(self):
        """Initialize market model"""
        self.alpha = None
        self.beta = None
        self.r_squared = None
        self.stderr_alpha = None
        self.stderr_beta = None
        self.residuals = None
        self.residual_std = None  # sqrt(MSE) from estimation window — for CAR tests
        self.sigma_squared = None
        self.estimation_window = config.ESTIMATION_WINDOW

    def estimate(
        self,
        stock_returns: pd.Series,
        market_returns: pd.Series,
        announcement_date: datetime,
        estimation_window: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Estimate market model parameters

        Parameters
        ----------
        stock_returns : pd.Series
            Stock returns time series
        market_returns : pd.Series
            Market returns time series
        announcement_date : datetime
            Announcement date (estimation uses data before this)
        estimation_window : int, optional
            Number of days for estimation (default from config)

        Returns
        -------
        dict
            Estimated parameters: alpha, beta, R², std errors
        """
        if estimation_window is None:
            estimation_window = self.estimation_window

        # Align and filter data
        data = pd.DataFrame({
            'stock': stock_returns,
            'market': market_returns
        }).dropna()

        # Convert announcement_date to timezone-aware if data has timezone
        if data.index.tz is not None and announcement_date.tzinfo is None:
            # Make announcement_date timezone-aware to match data
            announcement_date = pd.Timestamp(announcement_date).tz_localize(data.index.tz)
        elif data.index.tz is None and announcement_date.tzinfo is not None:
            # Remove timezone from announcement_date if data is timezone-naive
            announcement_date = pd.Timestamp(announcement_date).tz_localize(None)

        # Get estimation window (days before announcement)
        estimation_data = data[data.index < announcement_date].tail(estimation_window)

        if len(estimation_data) < estimation_window * 0.8:
            logger.warning(
                f"Insufficient estimation data: {len(estimation_data)} "
                f"(expected {estimation_window})"
            )

        # Extract returns
        y = estimation_data['stock'].values  # Stock returns
        X = estimation_data['market'].values  # Market returns

        # Estimate using OLS
        self._ols_regression(y, X)

        # Calculate fit statistics
        self._calculate_statistics(y, X)

        results = {
            'alpha': self.alpha,
            'beta': self.beta,
            'r_squared': self.r_squared,
            'stderr_alpha': self.stderr_alpha,
            'stderr_beta': self.stderr_beta,
            'n_observations': len(estimation_data),
            'residual_std': self.residual_std,
            'sigma_squared': self.sigma_squared,
            't_stat_alpha': self.alpha / self.stderr_alpha if self.stderr_alpha > 0 else 0,
            't_stat_beta': self.beta / self.stderr_beta if self.stderr_beta > 0 else 0,
        }

        logger.info(
            f"Market model estimated: α={self.alpha:.6f}, β={self.beta:.4f}, "
            f"R²={self.r_squared:.4f}, n={len(estimation_data)}"
        )

        return results

    def _ols_regression(self, y: np.ndarray, X: np.ndarray) -> None:
        """
        Perform OLS regression

        Parameters
        ----------
        y : np.ndarray
            Dependent variable (stock returns)
        X : np.ndarray
            Independent variable (market returns)
        """
        # Add constant term
        X_with_const = np.column_stack([np.ones(len(X)), X])

        # OLS: β = (X'X)^(-1) X'y
        try:
            beta_hat = np.linalg.lstsq(X_with_const, y, rcond=None)[0]
            self.alpha = beta_hat[0]
            self.beta = beta_hat[1]

            # Calculate residuals
            self.residuals = y - (self.alpha + self.beta * X)

        except np.linalg.LinAlgError as e:
            logger.error(f"OLS regression failed: {e}")
            self.alpha = np.mean(y)
            self.beta = 1.0
            self.residuals = np.zeros(len(y))

    def _calculate_statistics(self, y: np.ndarray, X: np.ndarray) -> None:
        """
        Calculate regression statistics

        Parameters
        ----------
        y : np.ndarray
            Dependent variable
        X : np.ndarray
            Independent variable
        """
        n = len(y)
        k = 2  # Number of parameters (alpha, beta)

        # R-squared
        y_pred = self.alpha + self.beta * X
        ss_res = np.sum(self.residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        self.r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Standard errors
        if n > k:
            # Variance of residuals (estimation-window error variance for event tests)
            self.sigma_squared = ss_res / (n - k)
            self.residual_std = float(np.sqrt(self.sigma_squared))

            # Variance-covariance matrix
            X_with_const = np.column_stack([np.ones(n), X])
            var_covar = self.sigma_squared * np.linalg.inv(X_with_const.T @ X_with_const)

            self.stderr_alpha = np.sqrt(var_covar[0, 0])
            self.stderr_beta = np.sqrt(var_covar[1, 1])
        else:
            self.sigma_squared = 0.0
            self.residual_std = 0.0
            self.stderr_alpha = 0
            self.stderr_beta = 0

    def predict(
        self,
        market_returns: pd.Series,
        return_confidence: bool = False,
        confidence_level: float = 0.95
    ) -> pd.Series:
        """
        Predict expected returns using estimated model

        Parameters
        ----------
        market_returns : pd.Series
            Market returns for prediction
        return_confidence : bool
            Whether to return confidence intervals
        confidence_level : float
            Confidence level for intervals

        Returns
        -------
        pd.Series or tuple
            Predicted returns (and confidence intervals if requested)
        """
        if self.alpha is None or self.beta is None:
            raise ValueError("Model not estimated. Call estimate() first.")

        expected_returns = self.alpha + self.beta * market_returns

        if return_confidence:
            # Calculate prediction intervals
            residual_std = np.std(self.residuals)
            z_score = stats.norm.ppf((1 + confidence_level) / 2)
            margin = z_score * residual_std

            lower_bound = expected_returns - margin
            upper_bound = expected_returns + margin

            return expected_returns, lower_bound, upper_bound

        return expected_returns

    def get_summary(self) -> str:
        """
        Get summary of model estimation

        Returns
        -------
        str
            Summary string
        """
        if self.alpha is None:
            return "Market model not estimated"

        t_alpha = self.alpha / self.stderr_alpha if self.stderr_alpha > 0 else 0
        t_beta = self.beta / self.stderr_beta if self.stderr_beta > 0 else 0

        summary = f"""
Market Model Estimation Summary
================================
α (Alpha):     {self.alpha:>10.6f}  (t={t_alpha:>6.2f})
β (Beta):      {self.beta:>10.4f}  (t={t_beta:>6.2f})
R²:            {self.r_squared:>10.4f}
Std Error α:   {self.stderr_alpha:>10.6f}
Std Error β:   {self.stderr_beta:>10.6f}
"""
        return summary

    def test_significance(self, alpha: float = 0.05) -> Dict[str, bool]:
        """
        Test parameter significance

        Parameters
        ----------
        alpha : float
            Significance level

        Returns
        -------
        dict
            Significance test results
        """
        if self.alpha is None:
            return {'alpha_significant': False, 'beta_significant': False}

        # Critical t-value (approximate for large samples)
        critical_t = stats.t.ppf(1 - alpha/2, df=100)

        t_alpha = abs(self.alpha / self.stderr_alpha) if self.stderr_alpha > 0 else 0
        t_beta = abs(self.beta / self.stderr_beta) if self.stderr_beta > 0 else 0

        return {
            'alpha_significant': t_alpha > critical_t,
            'beta_significant': t_beta > critical_t,
            't_stat_alpha': t_alpha,
            't_stat_beta': t_beta,
            'critical_value': critical_t
        }
