"""
Composite PEAD Score
Combines all scoring components into final score
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
import logging

from src.scoring.earnings_surprise import EarningsSurpriseScorer
from src.scoring.price_reaction import PriceReactionScorer
from src.scoring.drift_confirmation import DriftConfirmationScorer
from src.scoring.earnings_quality import EarningsQualityScorer
from src.scoring.contextual import ContextualScorer
from src.config.settings import config

logger = logging.getLogger(__name__)


class CompositeScorer:
    """
    Combine all scoring components into final PEAD score

    Components (default weights):
    1. Earnings Surprise: 25%
    2. Price Reaction: 20%
    3. Drift Confirmation: 25%
    4. Earnings Quality: 15%
    5. Contextual Factors: 15%
    """

    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        """
        Initialize composite scorer

        Parameters
        ----------
        custom_weights : dict, optional
            Custom component weights (must sum to 1.0)
        """
        self.weights = custom_weights or config.SCORING_WEIGHTS

        # Validate weights
        if abs(sum(self.weights.values()) - 1.0) > 0.01:
            logger.warning(
                f"Weights sum to {sum(self.weights.values()):.2f}, normalizing"
            )
            total = sum(self.weights.values())
            self.weights = {k: v/total for k, v in self.weights.items()}

        # Initialize component scorers
        self.earnings_scorer = EarningsSurpriseScorer()
        self.price_scorer = PriceReactionScorer()
        self.drift_scorer = DriftConfirmationScorer()
        self.quality_scorer = EarningsQualityScorer()
        self.contextual_scorer = ContextualScorer()

    def calculate_composite_score(
        self,
        earnings_surprise_data: Dict,
        price_reaction_data: Dict,
        drift_confirmation_data: Dict,
        earnings_quality_data: Dict,
        contextual_data: Dict,
        data_quality: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """
        Calculate composite PEAD score

        Parameters
        ----------
        earnings_surprise_data : dict
            Earnings surprise score components
        price_reaction_data : dict
            Price reaction score components
        drift_confirmation_data : dict
            Drift confirmation score components
        earnings_quality_data : dict
            Earnings quality score components
        contextual_data : dict
            Contextual score components
        data_quality : dict, optional
            Diagnostics (model fit, PDF/Yahoo coverage) used to scale confidence — not alpha.

        Returns
        -------
        dict
            Composite score and components
        """
        # Get component scores
        components = {
            'earnings_surprise': earnings_surprise_data.get('total', 0),
            'price_reaction': price_reaction_data.get('total', 0),
            'drift_confirmation': drift_confirmation_data.get('total', 0),
            'earnings_quality': earnings_quality_data.get('total', 0),
            'contextual': contextual_data.get('total', 0)
        }

        # Normalize component scores to 0-100 scale
        normalized = self._normalize_scores(components)

        # Calculate weighted composite score
        composite_score = sum(
            normalized[comp] * self.weights[comp]
            for comp in self.weights.keys()
        )

        # Calculate confidence level based on data availability
        confidence = self._calculate_confidence(components, data_quality)

        result = {
            'composite_score': composite_score,
            'components': components,
            'normalized_components': normalized,
            'weights': self.weights,
            'confidence': confidence,
            'rating': self._get_rating(composite_score),
            'recommendation': self._get_recommendation(composite_score, confidence),
            'data_quality': data_quality or {},
        }

        logger.info(
            f"Composite PEAD Score: {composite_score:.2f}/100 "
            f"(Rating: {result['rating']}, Confidence: {confidence:.0%})"
        )

        return result

    def _normalize_scores(self, components: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize component scores to 0-100 scale

        Parameters
        ----------
        components : dict
            Raw component scores

        Returns
        -------
        dict
            Normalized scores (0-100)
        """
        # Maximum possible scores for each component
        max_scores = {
            'earnings_surprise': 70,
            'price_reaction': 20,
            'drift_confirmation': 25,
            'earnings_quality': 15,
            'contextual': 15
        }

        normalized = {}
        for component, score in components.items():
            max_score = max_scores.get(component, 100)
            # Normalize to 0-100 scale (allow negative scores to go below 0)
            normalized_score = (score / max_score) * 100
            # Cap at reasonable bounds
            normalized[component] = max(min(normalized_score, 120), -20)

        return normalized

    def _calculate_confidence(
        self,
        components: Dict[str, float],
        data_quality: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Confidence in the composite score (coverage and model fit), not expected alpha.

        Parameters
        ----------
        components : dict
            Component scores
        data_quality : dict, optional
            Flags such as has_pdf_text, has_yahoo_yoy, r_squared, residual_std

        Returns
        -------
        float
            Confidence level (0-1)
        """
        dq = data_quality or {}

        available_components = sum(1 for score in components.values() if score != 0)
        total_components = len(components)
        base_confidence = available_components / total_components

        drift_score = components.get("drift_confirmation", 0)
        if drift_score > 15:
            base_confidence *= 1.1
        elif drift_score < 5:
            base_confidence *= 0.9

        r2 = dq.get("r_squared")
        if r2 is not None and np.isfinite(r2):
            if r2 < 0.05:
                base_confidence *= 0.82
            elif r2 < 0.15:
                base_confidence *= 0.92

        rs = dq.get("residual_std")
        if rs is None or (isinstance(rs, (int, float)) and (not np.isfinite(rs) or rs <= 0)):
            base_confidence *= 0.85

        if not dq.get("has_pdf_text") and not dq.get("has_yahoo_yoy"):
            base_confidence *= 0.78
        elif not dq.get("has_yahoo_yoy") and components.get("earnings_surprise", 0) == 0:
            base_confidence *= 0.88

        return float(min(max(base_confidence, 0.05), 1.0))

    def _get_rating(self, composite_score: float) -> str:
        """
        Convert numerical score to rating

        Parameters
        ----------
        composite_score : float
            Composite score

        Returns
        -------
        str
            Rating category
        """
        if composite_score >= 80:
            return "STRONG BUY"
        elif composite_score >= 65:
            return "BUY"
        elif composite_score >= 50:
            return "MODERATE BUY"
        elif composite_score >= 35:
            return "HOLD"
        elif composite_score >= 20:
            return "MODERATE SELL"
        elif composite_score >= 0:
            return "SELL"
        else:
            return "STRONG SELL"

    def _get_recommendation(
        self,
        composite_score: float,
        confidence: float
    ) -> str:
        """
        Generate trading recommendation

        Parameters
        ----------
        composite_score : float
            Composite score
        confidence : float
            Confidence level

        Returns
        -------
        str
            Recommendation text
        """
        if confidence < 0.5:
            return (
                f"INSUFFICIENT DATA - Score: {composite_score:.1f}/100 "
                f"(Confidence: {confidence:.0%}). Recommendation not reliable."
            )

        if composite_score >= 70:
            return (
                f"STRONG PEAD SIGNAL - Score: {composite_score:.1f}/100. "
                f"High probability of continued drift in announcement direction. "
                f"Consider entry for {config.CAR_WINDOWS[2]}-{config.CAR_WINDOWS[-2]} day horizon."
            )
        elif composite_score >= 55:
            return (
                f"MODERATE PEAD SIGNAL - Score: {composite_score:.1f}/100. "
                f"Positive drift likely. Consider position with appropriate risk management."
            )
        elif composite_score >= 40:
            return (
                f"WEAK PEAD SIGNAL - Score: {composite_score:.1f}/100. "
                f"Mixed signals. Monitor for confirmation before entry."
            )
        elif composite_score >= 20:
            return (
                f"NEUTRAL/NEGATIVE - Score: {composite_score:.1f}/100. "
                f"Drift unclear or negative. Avoid or consider opposite position."
            )
        else:
            return (
                f"STRONG NEGATIVE SIGNAL - Score: {composite_score:.1f}/100. "
                f"High probability of negative drift. Consider avoiding or shorting."
            )

    def get_detailed_report(self, score_data: Dict) -> str:
        """
        Generate detailed scoring report

        Parameters
        ----------
        score_data : dict
            Complete score data from calculate_composite_score

        Returns
        -------
        str
            Formatted report
        """
        report = "\n" + "="*70 + "\n"
        report += "PEAD COMPOSITE SCORE REPORT\n"
        report += "="*70 + "\n\n"

        # Overall score
        report += f"COMPOSITE SCORE: {score_data['composite_score']:.2f}/100\n"
        report += f"RATING: {score_data['rating']}\n"
        report += f"CONFIDENCE: {score_data['confidence']:.0%}\n"
        report += "\n" + "-"*70 + "\n\n"

        # Component breakdown
        report += "COMPONENT BREAKDOWN:\n\n"
        components = score_data['components']
        normalized = score_data['normalized_components']
        weights = score_data['weights']

        for component in components.keys():
            display_name = component.replace('_', ' ').title()
            raw = components[component]
            norm = normalized[component]
            weight = weights[component]
            contribution = norm * weight

            report += f"{display_name}:\n"
            report += f"  Raw Score:         {raw:>8.2f}\n"
            report += f"  Normalized (0-100):{norm:>8.2f}\n"
            report += f"  Weight:            {weight:>8.1%}\n"
            report += f"  Contribution:      {contribution:>8.2f}\n\n"

        report += "-"*70 + "\n\n"

        dq = score_data.get("data_quality") or {}
        if dq:
            report += "DATA COVERAGE (affects confidence, not alpha):\n"
            report += f"  PDF text parsed:        {'yes' if dq.get('has_pdf_text') else 'no'}\n"
            report += f"  Yahoo YoY fundamentals: {'yes' if dq.get('has_yahoo_yoy') else 'no'}\n"
            r2 = dq.get("r_squared")
            if r2 is not None and np.isfinite(r2):
                report += f"  Market model R²:       {r2:.4f}\n"
            report += "\n"

        # Recommendation
        report += "RECOMMENDATION:\n"
        report += score_data['recommendation'] + "\n\n"

        report += "="*70 + "\n"

        return report

    def export_to_dataframe(self, score_data: Dict, symbol: str) -> pd.DataFrame:
        """
        Export score data to DataFrame

        Parameters
        ----------
        score_data : dict
            Score data
        symbol : str
            Stock symbol

        Returns
        -------
        pd.DataFrame
            Score data as DataFrame
        """
        data = {
            'Symbol': symbol,
            'Composite_Score': score_data['composite_score'],
            'Rating': score_data['rating'],
            'Confidence': score_data['confidence'],
            **{f'{k}_raw': v for k, v in score_data['components'].items()},
            **{f'{k}_normalized': v for k, v in score_data['normalized_components'].items()}
        }

        return pd.DataFrame([data])
