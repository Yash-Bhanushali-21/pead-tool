"""
Configuration settings for PEAD analysis
Centralized configuration following single source of truth principle
"""
from dataclasses import dataclass
from typing import List, Dict
import os


@dataclass
class Config:
    """Configuration class for PEAD analysis parameters"""

    # Market Model Parameters
    ESTIMATION_WINDOW: int = 120  # Trading days for α, β estimation
    MARKET_INDEX: str = "^NSEI"   # NIFTY 50 as market proxy

    # CAR Windows (trading days)
    CAR_WINDOWS: List[int] = None

    # Scoring Weights
    SCORING_WEIGHTS: Dict[str, float] = None

    # Statistical Significance
    SIGNIFICANCE_LEVEL: float = 0.05  # 5% significance level

    # Data Parameters
    TOP_N_COMPANIES: int = 10  # Analyze top N recent announcements
    MIN_TRADING_DAYS: int = 150  # Minimum days of data required

    # PDF Download Settings
    PDF_DOWNLOAD_DIR: str = "./data/announcements"
    CACHE_DIR: str = "./data/cache"

    # Volume Spike Detection
    VOLUME_SPIKE_THRESHOLD: float = 2.0  # 2x average volume
    VOLUME_LOOKBACK: int = 20  # Days for volume average

    # Earnings Quality Thresholds
    CFO_QUALITY_THRESHOLD: float = 1.0  # CFO/Net Income ratio
    MARGIN_EXPANSION_THRESHOLD: float = 0.02  # 2% margin improvement

    # Drift Confirmation
    DRIFT_SHORT_WINDOW: int = 5
    DRIFT_MEDIUM_WINDOW: int = 10
    DRIFT_LONG_WINDOW: int = 30

    # Sentiment Analysis
    SENTIMENT_KEYWORDS_POSITIVE: List[str] = None
    SENTIMENT_KEYWORDS_NEGATIVE: List[str] = None

    def __post_init__(self):
        """Initialize default values for mutable fields"""
        if self.CAR_WINDOWS is None:
            self.CAR_WINDOWS = [1, 10, 30, 60, 90]

        if self.SCORING_WEIGHTS is None:
            self.SCORING_WEIGHTS = {
                'earnings_surprise': 0.25,
                'price_reaction': 0.20,
                'drift_confirmation': 0.25,
                'earnings_quality': 0.15,
                'contextual': 0.15
            }

        if self.SENTIMENT_KEYWORDS_POSITIVE is None:
            self.SENTIMENT_KEYWORDS_POSITIVE = [
                'beat', 'exceed', 'strong', 'growth', 'robust', 'positive',
                'expansion', 'improvement', 'record', 'highest', 'outperform'
            ]

        if self.SENTIMENT_KEYWORDS_NEGATIVE is None:
            self.SENTIMENT_KEYWORDS_NEGATIVE = [
                'miss', 'weak', 'decline', 'loss', 'concern', 'challenge',
                'deteriorate', 'poor', 'lower', 'negative', 'underperform'
            ]

        # Create directories if they don't exist
        os.makedirs(self.PDF_DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(self.CACHE_DIR, exist_ok=True)


# Global configuration instance
config = Config()
