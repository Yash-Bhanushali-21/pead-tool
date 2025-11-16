"""
Component 1: Earnings Surprise Scoring
Quantifies the magnitude and quality of earnings surprise
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class EarningsSurpriseScorer:
    """
    Score earnings surprise strength

    Factors:
    - EPS surprise (YoY, QoQ)
    - Revenue surprise
    - Margin expansion/contraction
    - Guidance (from PDF sentiment)
    """

    def __init__(self):
        """Initialize earnings surprise scorer"""
        self.max_score = 70  # Out of 100 total points

    def score(
        self,
        current_financials: Dict,
        previous_financials: Dict,
        pdf_analysis: Optional[Dict] = None
    ) -> Dict[str, float]:
        """
        Calculate earnings surprise score

        Parameters
        ----------
        current_financials : dict
            Current quarter/year financials
        previous_financials : dict
            Previous period for comparison
        pdf_analysis : dict, optional
            PDF analysis results (for guidance)

        Returns
        -------
        dict
            Score components and total
        """
        scores = {
            'eps_surprise': 0,
            'revenue_surprise': 0,
            'margin_surprise': 0,
            'guidance_score': 0,
            'total': 0
        }

        # 1. EPS Surprise (max 20 points)
        scores['eps_surprise'] = self._score_eps_surprise(
            current_financials, previous_financials
        )

        # 2. Revenue Surprise (max 15 points)
        scores['revenue_surprise'] = self._score_revenue_surprise(
            current_financials, previous_financials
        )

        # 3. Margin Surprise (max 20 points)
        scores['margin_surprise'] = self._score_margin_surprise(
            current_financials, previous_financials
        )

        # 4. Guidance (max 15 points)
        if pdf_analysis:
            scores['guidance_score'] = self._score_guidance(pdf_analysis)

        # Total score
        scores['total'] = sum([
            scores['eps_surprise'],
            scores['revenue_surprise'],
            scores['margin_surprise'],
            scores['guidance_score']
        ])

        logger.info(f"Earnings surprise total score: {scores['total']:.2f}")
        return scores

    def _score_eps_surprise(
        self,
        current: Dict,
        previous: Dict
    ) -> float:
        """
        Score EPS surprise

        Parameters
        ----------
        current : dict
            Current financials
        previous : dict
            Previous financials

        Returns
        -------
        float
            Score (0-20)
        """
        score = 0

        try:
            current_eps = current.get('eps', None)
            previous_eps = previous.get('eps', None)

            if current_eps and previous_eps and previous_eps != 0:
                # Calculate YoY/QoQ growth
                eps_growth = (current_eps - previous_eps) / abs(previous_eps)

                # Score based on growth magnitude
                if eps_growth > 0.30:  # >30% growth
                    score = 20
                elif eps_growth > 0.20:  # 20-30%
                    score = 17
                elif eps_growth > 0.10:  # 10-20%
                    score = 14
                elif eps_growth > 0.05:  # 5-10%
                    score = 10
                elif eps_growth > 0:  # Positive
                    score = 6
                elif eps_growth > -0.10:  # Small decline
                    score = -5
                else:  # Significant miss
                    score = -15

                logger.debug(f"EPS growth: {eps_growth:.2%}, score: {score}")

        except Exception as e:
            logger.warning(f"Error scoring EPS surprise: {e}")

        return score

    def _score_revenue_surprise(
        self,
        current: Dict,
        previous: Dict
    ) -> float:
        """
        Score revenue surprise

        Parameters
        ----------
        current : dict
            Current financials
        previous : dict
            Previous financials

        Returns
        -------
        float
            Score (0-15)
        """
        score = 0

        try:
            current_rev = current.get('revenue', None)
            previous_rev = previous.get('revenue', None)

            if current_rev and previous_rev and previous_rev != 0:
                revenue_growth = (current_rev - previous_rev) / abs(previous_rev)

                # Score based on growth
                if revenue_growth > 0.25:  # >25%
                    score = 15
                elif revenue_growth > 0.15:  # 15-25%
                    score = 12
                elif revenue_growth > 0.10:  # 10-15%
                    score = 10
                elif revenue_growth > 0.05:  # 5-10%
                    score = 7
                elif revenue_growth > 0:  # Positive
                    score = 4
                elif revenue_growth > -0.05:  # Small decline
                    score = -3
                else:  # Significant miss
                    score = -10

                logger.debug(f"Revenue growth: {revenue_growth:.2%}, score: {score}")

        except Exception as e:
            logger.warning(f"Error scoring revenue surprise: {e}")

        return score

    def _score_margin_surprise(
        self,
        current: Dict,
        previous: Dict
    ) -> float:
        """
        Score margin expansion/contraction

        Parameters
        ----------
        current : dict
            Current financials
        previous : dict
            Previous financials

        Returns
        -------
        float
            Score (0-20)
        """
        score = 0

        try:
            # Try to get margins (EBITDA margin, net margin, etc.)
            current_margin = current.get('operating_margin',
                                        current.get('net_margin', None))
            previous_margin = previous.get('operating_margin',
                                          previous.get('net_margin', None))

            if current_margin is not None and previous_margin is not None:
                margin_change = current_margin - previous_margin

                # Score based on margin change (in percentage points)
                if margin_change > 5:  # >5pp expansion
                    score = 20
                elif margin_change > 3:  # 3-5pp
                    score = 16
                elif margin_change > 1:  # 1-3pp
                    score = 12
                elif margin_change > 0:  # Positive
                    score = 8
                elif margin_change > -1:  # Slight contraction
                    score = -3
                elif margin_change > -3:  # Moderate contraction
                    score = -8
                else:  # Severe contraction
                    score = -15

                logger.debug(f"Margin change: {margin_change:.2f}pp, score: {score}")

            # Alternative: calculate margin from available data
            elif current.get('ebitda') and current.get('revenue'):
                current_calc_margin = (current['ebitda'] / current['revenue']) * 100
                if previous.get('ebitda') and previous.get('revenue'):
                    previous_calc_margin = (previous['ebitda'] / previous['revenue']) * 100
                    margin_change = current_calc_margin - previous_calc_margin

                    # Apply same scoring logic
                    if margin_change > 5:
                        score = 20
                    elif margin_change > 3:
                        score = 16
                    elif margin_change > 1:
                        score = 12
                    elif margin_change > 0:
                        score = 8
                    else:
                        score = max(-15, -margin_change * 3)

        except Exception as e:
            logger.warning(f"Error scoring margin surprise: {e}")

        return score

    def _score_guidance(self, pdf_analysis: Dict) -> float:
        """
        Score forward guidance from PDF analysis

        Parameters
        ----------
        pdf_analysis : dict
            PDF analysis with guidance info

        Returns
        -------
        float
            Score (0-15)
        """
        score = 0

        try:
            guidance = pdf_analysis.get('guidance', {})
            sentiment = pdf_analysis.get('sentiment', {})

            # Has explicit guidance
            if guidance.get('has_guidance', False):
                score += 5

                # Positive signals in guidance
                guidance_sentiment = guidance.get('guidance_sentiment', 0)
                score += guidance_sentiment * 10  # Max 10 points

            # No guidance but positive announcement sentiment
            elif sentiment.get('sentiment_score', 0) > 0.3:
                score += 5

        except Exception as e:
            logger.warning(f"Error scoring guidance: {e}")

        return min(score, 15)  # Cap at 15

    def get_surprise_direction(self, score: float) -> str:
        """
        Get qualitative description of surprise

        Parameters
        ----------
        score : float
            Total earnings surprise score

        Returns
        -------
        str
            Description
        """
        if score > 50:
            return "Strong Positive Surprise"
        elif score > 30:
            return "Positive Surprise"
        elif score > 10:
            return "Mild Positive Surprise"
        elif score > -10:
            return "In-line / No Surprise"
        elif score > -30:
            return "Mild Negative Surprise"
        else:
            return "Negative Surprise"
