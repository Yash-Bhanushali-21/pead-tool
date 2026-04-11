"""Trade readiness / execution context scoring."""
import unittest
from datetime import datetime

import numpy as np
import pandas as pd

from src.trade_context.trade_readiness import compute_trade_context


def _dummy_ohlcv(n: int = 80) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    close = np.linspace(100, 110, n)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.linspace(1e6, 1.2e6, n),
        },
        index=idx,
    )


class TestTradeReadiness(unittest.TestCase):
    def test_compute_trade_context_shape(self):
        df = _dummy_ohlcv()
        results = {
            "composite_score": {"rating": "BUY", "data_quality": {"r_squared": 0.12}},
            "fundamental_analysis": {"stance": "constructive"},
            "technical_analysis": {
                "stance": "bullish structure",
                "last": {"atr_pct": 0.022},
            },
            "news_sentiment": {"news_score_0_100": 62.0},
            "market_model": {"beta": 0.95, "r_squared": 0.12},
        }
        tc = compute_trade_context(results, df)
        self.assertIn("trade_readiness_score_0_100", tc)
        self.assertGreaterEqual(tc["trade_readiness_score_0_100"], 0.0)
        self.assertLessEqual(tc["trade_readiness_score_0_100"], 100.0)
        self.assertIn("pillars", tc)
        self.assertIn("risk_flags", tc)


if __name__ == "__main__":
    unittest.main()
