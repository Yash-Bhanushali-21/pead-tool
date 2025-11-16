"""
Component 5: Contextual Factors Scoring
Incorporates sector, company characteristics, and macro environment
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ContextualScorer:
    """
    Score contextual factors

    Factors:
    - Market cap category (mid-cap best for PEAD)
    - Sector tailwinds
    - Company track record
    - Market environment (volatility)
    """

    def __init__(self):
        """Initialize contextual scorer"""
        self.max_score = 15

    def score(
        self,
        company_info: Dict,
        market_data: Optional[pd.DataFrame] = None,
        historical_results: Optional[Dict] = None
    ) -> Dict[str, float]:
        """
        Calculate contextual score

        Parameters
        ----------
        company_info : dict
            Company information
        market_data : pd.DataFrame, optional
            Market index data for volatility
        historical_results : dict, optional
            Company's historical earnings track record

        Returns
        -------
        dict
            Score components and total
        """
        scores = {
            'market_cap_score': 0,
            'sector_score': 0,
            'track_record': 0,
            'macro_environment': 0,
            'total': 0
        }

        # 1. Market cap category (max 5 points)
        scores['market_cap_score'] = self._score_market_cap(company_info)

        # 2. Sector tailwinds (max 4 points)
        scores['sector_score'] = self._score_sector(company_info)

        # 3. Historical track record (max 3 points)
        if historical_results:
            scores['track_record'] = self._score_track_record(historical_results)

        # 4. Macro environment (max 3 points)
        if market_data is not None:
            scores['macro_environment'] = self._score_macro(market_data)

        scores['total'] = sum([
            scores['market_cap_score'],
            scores['sector_score'],
            scores['track_record'],
            scores['macro_environment']
        ])

        logger.info(f"Contextual score: {scores['total']:.2f}")
        return scores

    def _score_market_cap(self, company_info: Dict) -> float:
        """
        Score based on market cap category

        Mid-caps typically show strongest PEAD
        Large-caps: quick price adjustment
        Small-caps: high noise

        Parameters
        ----------
        company_info : dict
            Company information

        Returns
        -------
        float
            Score (0-5)
        """
        market_cap = company_info.get('market_cap', 0)

        if market_cap == 0:
            return 2  # Unknown, neutral score

        # Convert to billions (if needed)
        if market_cap > 1e12:  # Already in small units
            market_cap_b = market_cap / 1e9
        else:
            market_cap_b = market_cap

        # Indian market cap categories (approximate in USD)
        if 1 <= market_cap_b <= 10:  # Mid-cap (best for PEAD)
            score = 5
        elif 0.3 <= market_cap_b < 1:  # Small-cap
            score = 3
        elif 10 < market_cap_b <= 50:  # Large-cap
            score = 2
        elif market_cap_b > 50:  # Mega-cap (efficient pricing)
            score = 1
        else:  # Micro-cap (too much noise)
            score = 1

        logger.debug(f"Market cap: ${market_cap_b:.2f}B, score: {score}")
        return score

    def _score_sector(self, company_info: Dict) -> float:
        """
        Score based on sector tailwinds

        (Simplified - ideally would incorporate current sector trends)

        Parameters
        ----------
        company_info : dict
            Company information

        Returns
        -------
        float
            Score (0-4)
        """
        sector = company_info.get('sector', '').lower()
        industry = company_info.get('industry', '').lower()

        # Sector scoring (simplified - you can customize based on current trends)
        favorable_sectors = {
            'technology': 4,
            'information technology': 4,
            'healthcare': 3,
            'pharmaceuticals': 3,
            'consumer discretionary': 3,
            'financials': 2,
            'industrials': 2,
            'materials': 2,
            'utilities': 1,
            'energy': 2,
        }

        score = 2  # Default neutral

        for sector_name, sector_score in favorable_sectors.items():
            if sector_name in sector or sector_name in industry:
                score = sector_score
                break

        logger.debug(f"Sector: {sector}, score: {score}")
        return score

    def _score_track_record(self, historical_results: Dict) -> float:
        """
        Score based on company's earnings track record

        Consistent beaters → stronger drift
        Serial missers → weaker/negative drift

        Parameters
        ----------
        historical_results : dict
            Historical earnings performance

        Returns
        -------
        float
            Score (0-3)
        """
        # This is simplified - ideally you'd track historical surprises
        consistent_beats = historical_results.get('consistent_beats', 0)
        total_results = historical_results.get('total_results', 1)

        if total_results == 0:
            return 1

        beat_rate = consistent_beats / total_results

        if beat_rate > 0.75:  # Consistent beater
            score = 3
        elif beat_rate > 0.60:
            score = 2
        elif beat_rate > 0.40:
            score = 1
        else:  # Serial misser
            score = -1

        logger.debug(f"Beat rate: {beat_rate:.2%}, score: {score}")
        return score

    def _score_macro(self, market_data: pd.DataFrame) -> float:
        """
        Score based on macro environment

        Low VIX → smooth drift
        High VIX → drift breaks quickly

        Parameters
        ----------
        market_data : pd.DataFrame
            Market index data

        Returns
        -------
        float
            Score (0-3)
        """
        score = 2  # Default neutral

        try:
            # Calculate realized volatility (last 20 days)
            recent = market_data.tail(20)
            volatility = recent['Return'].std() * np.sqrt(252)  # Annualized

            # Score based on volatility regime
            if volatility < 0.15:  # Low vol (good for drift)
                score = 3
            elif volatility < 0.25:  # Normal vol
                score = 2
            elif volatility < 0.35:  # Elevated vol
                score = 1
            else:  # High vol (drift unreliable)
                score = 0

            logger.debug(f"Market volatility: {volatility:.2%}, score: {score}")

        except Exception as e:
            logger.warning(f"Error scoring macro environment: {e}")

        return score

    def get_governance_flags(self, company_info: Dict) -> Dict[str, bool]:
        """
        Check for corporate governance flags

        (Simplified - would integrate with governance databases)

        Parameters
        ----------
        company_info : dict
            Company information

        Returns
        -------
        dict
            Governance flags
        """
        # Placeholder - integrate with actual governance data
        flags = {
            'promoter_pledge_high': False,  # High promoter pledging
            'frequent_auditor_changes': False,
            'related_party_issues': False,
            'regulatory_issues': False,
            'governance_score': 7  # Out of 10
        }

        # If available, extract from company_info
        # This would come from external data sources

        return flags
