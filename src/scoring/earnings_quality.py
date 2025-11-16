"""
Component 4: Earnings Quality Scoring
Assesses quality of reported earnings
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

from ..config.settings import config

logger = logging.getLogger(__name__)


class EarningsQualityScorer:
    """
    Score earnings quality

    Factors:
    - Source of EPS beat (revenue vs cost cutting)
    - Cash flow confirmation
    - Balance sheet quality
    - One-offs / exceptional items
    """

    def __init__(self):
        """Initialize earnings quality scorer"""
        self.max_score = 15

    def score(
        self,
        current_financials: Dict,
        previous_financials: Dict,
        cash_flow_data: Optional[Dict] = None
    ) -> Dict[str, float]:
        """
        Calculate earnings quality score

        Parameters
        ----------
        current_financials : dict
            Current period financials
        previous_financials : dict
            Previous period financials
        cash_flow_data : dict, optional
            Cash flow statement data

        Returns
        -------
        dict
            Score components and total
        """
        scores = {
            'earnings_source': 0,
            'cash_flow_quality': 0,
            'balance_sheet_quality': 0,
            'total': 0
        }

        # 1. Source of earnings (max 6 points)
        scores['earnings_source'] = self._score_earnings_source(
            current_financials, previous_financials
        )

        # 2. Cash flow quality (max 6 points)
        if cash_flow_data:
            scores['cash_flow_quality'] = self._score_cash_flow(
                current_financials, cash_flow_data
            )

        # 3. Balance sheet quality (max 3 points)
        scores['balance_sheet_quality'] = self._score_balance_sheet(
            current_financials, previous_financials
        )

        scores['total'] = sum([
            scores['earnings_source'],
            scores['cash_flow_quality'],
            scores['balance_sheet_quality']
        ])

        logger.info(f"Earnings quality score: {scores['total']:.2f}")
        return scores

    def _score_earnings_source(
        self,
        current: Dict,
        previous: Dict
    ) -> float:
        """
        Score source of earnings growth

        Real revenue growth > Cost cutting > One-offs

        Parameters
        ----------
        current : dict
            Current financials
        previous : dict
            Previous financials

        Returns
        -------
        float
            Score (0-6)
        """
        score = 0

        try:
            # Get metrics
            curr_revenue = current.get('revenue', 0)
            prev_revenue = previous.get('revenue', 0)
            curr_profit = current.get('net_profit', 0)
            prev_profit = previous.get('net_profit', 0)

            if prev_revenue == 0 or prev_profit == 0:
                return 0

            revenue_growth = (curr_revenue - prev_revenue) / prev_revenue
            profit_growth = (curr_profit - prev_profit) / prev_profit

            # Best: Revenue growth + Profit growth (operating leverage)
            if revenue_growth > 0.10 and profit_growth > revenue_growth:
                score = 6  # High quality - operating leverage
            elif revenue_growth > 0.10 and profit_growth > 0:
                score = 5  # Good - revenue driven
            elif revenue_growth > 0 and profit_growth > revenue_growth:
                score = 4  # Moderate - some operating leverage
            elif revenue_growth > 0 and profit_growth > 0:
                score = 3  # Okay - in-line growth
            elif revenue_growth < 0 and profit_growth > 0:
                score = 1  # Weak - cost cutting driven
            else:
                score = 0

            logger.debug(
                f"Revenue growth: {revenue_growth:.2%}, "
                f"Profit growth: {profit_growth:.2%}, score: {score}"
            )

        except Exception as e:
            logger.warning(f"Error scoring earnings source: {e}")

        return score

    def _score_cash_flow(
        self,
        financials: Dict,
        cash_flow_data: Dict
    ) -> float:
        """
        Score cash flow quality

        CFO > Net Income = high quality
        CFO < Net Income = low quality (accrual accounting)

        Parameters
        ----------
        financials : dict
            Financial data
        cash_flow_data : dict
            Cash flow statement

        Returns
        -------
        float
            Score (0-6)
        """
        score = 0

        try:
            net_income = financials.get('net_profit', 0)

            # Extract CFO from cash flow data
            cfo = cash_flow_data.get('operating_cash_flow',
                                     cash_flow_data.get('cfo', 0))

            if net_income <= 0 or cfo is None:
                return 0

            # CFO / Net Income ratio
            cfo_ratio = cfo / net_income

            # Score based on ratio
            if cfo_ratio > 1.3:  # CFO significantly > NI
                score = 6  # Excellent quality
            elif cfo_ratio > 1.0:  # CFO > NI
                score = 5  # Good quality
            elif cfo_ratio > 0.8:  # Close to NI
                score = 3  # Acceptable
            elif cfo_ratio > 0.5:  # CFO lower
                score = 1  # Weak
            else:  # CFO much lower
                score = -3  # Poor quality (aggressive accounting)

            logger.debug(f"CFO/NI ratio: {cfo_ratio:.2f}, score: {score}")

        except Exception as e:
            logger.warning(f"Error scoring cash flow: {e}")

        return score

    def _score_balance_sheet(
        self,
        current: Dict,
        previous: Dict
    ) -> float:
        """
        Score balance sheet quality

        Check working capital trends, receivables, inventory

        Parameters
        ----------
        current : dict
            Current financials
        previous : dict
            Previous financials

        Returns
        -------
        float
            Score (0-3)
        """
        score = 2  # Start with neutral

        try:
            # Check for deteriorating working capital
            # (This is a simplified version - ideally we'd look at
            #  receivables days, inventory days, etc.)

            curr_assets = current.get('current_assets', 0)
            curr_liabilities = current.get('current_liabilities', 0)
            prev_assets = previous.get('current_assets', 0)
            prev_liabilities = previous.get('current_liabilities', 0)

            if curr_liabilities > 0 and prev_liabilities > 0:
                curr_ratio = curr_assets / curr_liabilities
                prev_ratio = prev_assets / prev_liabilities

                # Improving liquidity
                if curr_ratio > prev_ratio and curr_ratio > 1.5:
                    score = 3
                elif curr_ratio > prev_ratio:
                    score = 2
                # Deteriorating liquidity
                elif curr_ratio < prev_ratio and curr_ratio < 1.0:
                    score = -2
                elif curr_ratio < prev_ratio:
                    score = 1

            logger.debug(f"Balance sheet score: {score}")

        except Exception as e:
            logger.warning(f"Error scoring balance sheet: {e}")

        return score
