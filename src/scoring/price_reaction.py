"""
Component 2: Price Reaction Scoring
Analyzes immediate market reaction to announcement
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

from src.config.settings import config

logger = logging.getLogger(__name__)


class PriceReactionScorer:
    """
    Score price reaction on announcement day

    Factors:
    - Day 0 return magnitude
    - Volume spike
    - Gap open
    - Volatility changes
    """

    def __init__(self):
        """Initialize price reaction scorer"""
        self.max_score = 20

    def score(
        self,
        stock_data: pd.DataFrame,
        announcement_date: pd.Timestamp,
        earnings_direction: float = 0
    ) -> Dict[str, float]:
        """
        Calculate price reaction score

        Parameters
        ----------
        stock_data : pd.DataFrame
            Stock OHLCV data
        announcement_date : pd.Timestamp
            Announcement date
        earnings_direction : float
            Direction of earnings surprise (+1 positive, -1 negative, 0 neutral)

        Returns
        -------
        dict
            Score components and total
        """
        scores = {
            'day0_reaction': 0,
            'volume_spike': 0,
            'gap_score': 0,
            'total': 0
        }

        # Normalize timezone - match announcement_date timezone to stock_data.index
        if stock_data.index.tz is not None and announcement_date.tzinfo is None:
            announcement_date = pd.Timestamp(announcement_date).tz_localize(stock_data.index.tz)
        elif stock_data.index.tz is None and announcement_date.tzinfo is not None:
            announcement_date = pd.Timestamp(announcement_date).tz_localize(None)

        # Find announcement day data
        if announcement_date not in stock_data.index:
            # Find nearest date
            nearby = stock_data.index[stock_data.index >= announcement_date]
            if len(nearby) == 0:
                logger.warning("No price data for announcement date")
                return scores
            announcement_date = nearby[0]

        day0_data = stock_data.loc[announcement_date]

        # 1. Day 0 Reaction (max 10 points)
        scores['day0_reaction'] = self._score_day0_reaction(
            day0_data, earnings_direction
        )

        # 2. Volume Spike (max 6 points)
        scores['volume_spike'] = self._score_volume_spike(
            stock_data, announcement_date
        )

        # 3. Gap Open (max 4 points)
        scores['gap_score'] = self._score_gap(
            stock_data, announcement_date, earnings_direction
        )

        scores['total'] = sum([
            scores['day0_reaction'],
            scores['volume_spike'],
            scores['gap_score']
        ])

        logger.info(f"Price reaction score: {scores['total']:.2f}")
        return scores

    def _score_day0_reaction(
        self,
        day0_data: pd.Series,
        earnings_direction: float
    ) -> float:
        """
        Score day 0 price reaction

        Best PEAD scenario: Small reaction despite big earnings surprise
        This indicates market under-reaction → future drift potential

        Parameters
        ----------
        day0_data : pd.Series
            Day 0 OHLCV data
        earnings_direction : float
            Earnings surprise direction

        Returns
        -------
        float
            Score (0-10)
        """
        day0_return = day0_data.get('Return', 0)

        # PEAD logic: We want UNDER-reaction
        # Small move + big earnings = high future drift potential
        abs_return = abs(day0_return)

        if earnings_direction > 0:  # Positive earnings
            if 0 < day0_return < 0.02:  # Small positive move (0-2%)
                score = 10  # Best PEAD scenario
            elif 0.02 <= day0_return < 0.05:  # Moderate move
                score = 6
            elif day0_return >= 0.05:  # Large move (already priced in)
                score = 3
            elif day0_return < 0:  # Wrong direction
                score = -5
            else:
                score = 5

        elif earnings_direction < 0:  # Negative earnings
            if -0.02 < day0_return < 0:  # Small negative move
                score = 10
            elif -0.05 <= day0_return < -0.02:  # Moderate move
                score = 6
            elif day0_return <= -0.05:  # Large move (priced in)
                score = 3
            elif day0_return > 0:  # Wrong direction
                score = -5
            else:
                score = 5

        else:  # Neutral earnings
            # For neutral, we want minimal reaction
            if abs_return < 0.01:
                score = 5
            else:
                score = 0

        logger.debug(f"Day 0 return: {day0_return:.2%}, score: {score}")
        return score

    def _score_volume_spike(
        self,
        stock_data: pd.DataFrame,
        announcement_date: pd.Timestamp
    ) -> float:
        """
        Score volume spike on announcement

        High volume confirms market attention and conviction

        Parameters
        ----------
        stock_data : pd.DataFrame
            Stock data
        announcement_date : pd.Timestamp
            Announcement date

        Returns
        -------
        float
            Score (0-6)
        """
        score = 0

        try:
            # Get historical average volume
            pre_announcement = stock_data[
                stock_data.index < announcement_date
            ].tail(config.VOLUME_LOOKBACK)

            if len(pre_announcement) < 5:
                return 0

            avg_volume = pre_announcement['Volume'].mean()
            day0_volume = stock_data.loc[announcement_date, 'Volume']

            if avg_volume == 0:
                return 0

            volume_ratio = day0_volume / avg_volume

            # Score based on volume spike
            if volume_ratio > 5:  # 5x volume
                score = 6
            elif volume_ratio > 3:  # 3x volume
                score = 5
            elif volume_ratio > 2:  # 2x volume
                score = 4
            elif volume_ratio > 1.5:  # 1.5x volume
                score = 3
            elif volume_ratio > 1:  # Above average
                score = 1
            else:  # Below average (weak)
                score = -2

            logger.debug(f"Volume ratio: {volume_ratio:.2f}x, score: {score}")

        except Exception as e:
            logger.warning(f"Error scoring volume spike: {e}")

        return score

    def _score_gap(
        self,
        stock_data: pd.DataFrame,
        announcement_date: pd.Timestamp,
        earnings_direction: float
    ) -> float:
        """
        Score gap open on announcement day

        Parameters
        ----------
        stock_data : pd.DataFrame
            Stock data
        announcement_date : pd.Timestamp
            Announcement date
        earnings_direction : float
            Earnings direction

        Returns
        -------
        float
            Score (0-4)
        """
        score = 0

        try:
            idx = stock_data.index.get_loc(announcement_date)

            if idx == 0:
                return 0

            previous_close = stock_data.iloc[idx - 1]['Close']
            day0_open = stock_data.iloc[idx]['Open']
            day0_close = stock_data.iloc[idx]['Close']

            gap_pct = (day0_open - previous_close) / previous_close

            # Gap in earnings direction
            if earnings_direction > 0 and gap_pct > 0.01:  # Positive gap
                score = 4
                # Check if gap was held
                if day0_close >= day0_open:
                    score += 1  # Bonus for holding gap
            elif earnings_direction < 0 and gap_pct < -0.01:  # Negative gap
                score = 4
                if day0_close <= day0_open:
                    score += 1

            logger.debug(f"Gap: {gap_pct:.2%}, score: {score}")

        except Exception as e:
            logger.warning(f"Error scoring gap: {e}")

        return min(score, 4)  # Cap at 4
