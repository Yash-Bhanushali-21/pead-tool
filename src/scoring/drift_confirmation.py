"""
Component 3: Drift Confirmation Scoring
Analyzes post-announcement drift behavior
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

from src.config.config import config

logger = logging.getLogger(__name__)


class DriftConfirmationScorer:
    """
    Score drift confirmation signals

    Factors:
    - CAR magnitude and significance
    - Relative strength vs market
    - Trend continuation indicators
    - No early reversal
    """

    def __init__(self):
        """Initialize drift confirmation scorer"""
        self.max_score = 25

    def score(
        self,
        car_data: Dict,
        stock_data: pd.DataFrame,
        market_data: pd.DataFrame,
        announcement_date: pd.Timestamp
    ) -> Dict[str, float]:
        """
        Calculate drift confirmation score

        Parameters
        ----------
        car_data : dict
            CAR values for different windows
        stock_data : pd.DataFrame
            Stock price data
        market_data : pd.DataFrame
            Market index data
        announcement_date : pd.Timestamp
            Announcement date

        Returns
        -------
        dict
            Score components and total
        """
        scores = {
            'car_magnitude': 0,
            'car_significance': 0,
            'relative_strength': 0,
            'trend_continuity': 0,
            'no_reversal': 0,
            'total': 0
        }

        # Normalize timezone - match announcement_date timezone to stock_data.index
        if stock_data.index.tz is not None and announcement_date.tzinfo is None:
            announcement_date = pd.Timestamp(announcement_date).tz_localize(stock_data.index.tz)
        elif stock_data.index.tz is None and announcement_date.tzinfo is not None:
            announcement_date = pd.Timestamp(announcement_date).tz_localize(None)

        # 1. CAR Magnitude (max 8 points)
        scores['car_magnitude'] = self._score_car_magnitude(car_data)

        # 2. Statistical Significance (max 7 points)
        scores['car_significance'] = self._score_car_significance(car_data)

        # 3. Relative Strength (max 5 points)
        scores['relative_strength'] = self._score_relative_strength(
            stock_data, market_data, announcement_date
        )

        # 4. Trend Continuity (max 3 points)
        scores['trend_continuity'] = self._score_trend_continuity(
            stock_data, announcement_date
        )

        # 5. No Early Reversal (max 2 points)
        scores['no_reversal'] = self._score_no_reversal(
            stock_data, announcement_date
        )

        scores['total'] = sum([
            scores['car_magnitude'],
            scores['car_significance'],
            scores['relative_strength'],
            scores['trend_continuity'],
            scores['no_reversal']
        ])

        logger.info(f"Drift confirmation score: {scores['total']:.2f}")
        return scores

    def _score_car_magnitude(self, car_data: Dict) -> float:
        """
        Score CAR magnitudes across windows

        Weighted toward short-medium windows (1-30 days)

        Parameters
        ----------
        car_data : dict
            CAR values

        Returns
        -------
        float
            Score (0-8)
        """
        score = 0

        # Define weights for different windows
        window_weights = {
            1: 0.15,
            10: 0.30,
            30: 0.35,
            60: 0.15,
            90: 0.05
        }

        for window, weight in window_weights.items():
            if window in car_data:
                car = car_data[window].get('car', 0)
                abs_car = abs(car)

                # Score based on CAR magnitude
                if abs_car > 0.10:  # >10% CAR
                    window_score = 8
                elif abs_car > 0.07:  # 7-10%
                    window_score = 6
                elif abs_car > 0.04:  # 4-7%
                    window_score = 5
                elif abs_car > 0.02:  # 2-4%
                    window_score = 3
                elif abs_car > 0.01:  # 1-2%
                    window_score = 1
                else:
                    window_score = 0

                score += window_score * weight

        logger.debug(f"CAR magnitude score: {score:.2f}")
        return score

    def _score_car_significance(self, car_data: Dict) -> float:
        """
        Score statistical significance of CARs

        Parameters
        ----------
        car_data : dict
            CAR values

        Returns
        -------
        float
            Score (0-7)
        """
        score = 0

        # Count significant windows
        significant_windows = [
            w for w, data in car_data.items()
            if data.get('significant', False)
        ]

        # Score based on number of significant windows
        n_sig = len(significant_windows)
        if n_sig >= 4:
            score = 7
        elif n_sig == 3:
            score = 5
        elif n_sig == 2:
            score = 3
        elif n_sig == 1:
            score = 1

        # Penalty for weak p-values
        avg_p_value = np.mean([
            car_data[w].get('p_value', 1)
            for w in car_data
        ])

        if avg_p_value > 0.10:
            score *= 0.5  # Reduce score for weak significance

        logger.debug(f"Significance score: {score:.2f} ({n_sig} significant windows)")
        return score

    def _score_relative_strength(
        self,
        stock_data: pd.DataFrame,
        market_data: pd.DataFrame,
        announcement_date: pd.Timestamp
    ) -> float:
        """
        Score relative strength vs market index

        Parameters
        ----------
        stock_data : pd.DataFrame
            Stock data
        market_data : pd.DataFrame
            Market data
        announcement_date : pd.Timestamp
            Announcement date

        Returns
        -------
        float
            Score (0-5)
        """
        score = 0

        try:
            # Get post-announcement data
            stock_post = stock_data[stock_data.index >= announcement_date].head(30)
            market_post = market_data[market_data.index >= announcement_date].head(30)

            if len(stock_post) < 10 or len(market_post) < 10:
                return 0

            # Calculate cumulative returns
            stock_cum_return = (1 + stock_post['Return']).prod() - 1
            market_cum_return = (1 + market_post['Return']).prod() - 1

            # Relative performance
            relative_perf = stock_cum_return - market_cum_return

            # Score based on outperformance
            if relative_perf > 0.10:  # >10% outperformance
                score = 5
            elif relative_perf > 0.05:  # 5-10%
                score = 4
            elif relative_perf > 0.02:  # 2-5%
                score = 3
            elif relative_perf > 0:  # Positive
                score = 1
            else:  # Underperformance
                score = -3

            logger.debug(f"Relative performance: {relative_perf:.2%}, score: {score}")

        except Exception as e:
            logger.warning(f"Error scoring relative strength: {e}")

        return score

    def _score_trend_continuity(
        self,
        stock_data: pd.DataFrame,
        announcement_date: pd.Timestamp
    ) -> float:
        """
        Score trend continuity using technical indicators

        Parameters
        ----------
        stock_data : pd.DataFrame
            Stock data
        announcement_date : pd.Timestamp
            Announcement date

        Returns
        -------
        float
            Score (0-3)
        """
        score = 0

        try:
            post = stock_data[stock_data.index >= announcement_date].head(30)

            if len(post) < 20:
                return 0

            # Calculate moving averages
            post_copy = post.copy()
            post_copy['MA5'] = post_copy['Close'].rolling(5).mean()
            post_copy['MA20'] = post_copy['Close'].rolling(20).mean()

            # Trend indicators
            # 1. MA5 > MA20 (uptrend)
            if post_copy['MA5'].iloc[-1] > post_copy['MA20'].iloc[-1]:
                score += 1

            # 2. Higher highs and higher lows
            recent = post_copy.tail(10)
            if recent['High'].is_monotonic_increasing:
                score += 1

            # 3. Positive 5-day ROC
            roc = (post_copy['Close'].iloc[-1] / post_copy['Close'].iloc[-5] - 1)
            if roc > 0.02:
                score += 1

            logger.debug(f"Trend continuity score: {score}")

        except Exception as e:
            logger.warning(f"Error scoring trend continuity: {e}")

        return score

    def _score_no_reversal(
        self,
        stock_data: pd.DataFrame,
        announcement_date: pd.Timestamp
    ) -> float:
        """
        Check for early reversal (within 3 days)

        Parameters
        ----------
        stock_data : pd.DataFrame
            Stock data
        announcement_date : pd.Timestamp
            Announcement date

        Returns
        -------
        float
            Score (0-2)
        """
        score = 2  # Start with full points

        try:
            post = stock_data[stock_data.index >= announcement_date].head(5)

            if len(post) < 3:
                return score

            # Check first 3 days
            first_day_return = post['Return'].iloc[0]
            next_3_days_return = (1 + post['Return'].iloc[1:4]).prod() - 1

            # If major reversal (opposite direction and > 3%)
            if (first_day_return > 0.01 and next_3_days_return < -0.03) or \
               (first_day_return < -0.01 and next_3_days_return > 0.03):
                score = -5  # Penalty for reversal
                logger.debug("Early reversal detected")

        except Exception as e:
            logger.warning(f"Error checking reversal: {e}")

        return score
