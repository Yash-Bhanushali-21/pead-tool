"""Unit tests for CAR inference (estimation-window sigma)."""
import unittest
import numpy as np
import pandas as pd

from src.models.car import CumulativeAbnormalReturns


class TestCumulativeAbnormalReturns(unittest.TestCase):
    def test_car_uses_estimation_sigma_for_t_stat(self):
        """CAR t-stat should use σ_ε from the market model, not post-event sample σ(AR)."""
        n = 30
        ar = pd.DataFrame({"AR": np.full(n, 0.01)})
        sigma = 0.01
        est_df = 118

        calc = CumulativeAbnormalReturns()
        out = calc.calculate(
            ar,
            windows=[n],
            estimation_residual_std=sigma,
            estimation_t_df=est_df,
        )
        car = out[n]["car"]
        self.assertAlmostEqual(car, n * 0.01)
        se = sigma * np.sqrt(n)
        self.assertAlmostEqual(out[n]["t_statistic"], car / se)
        self.assertTrue(out[n]["car_test_uses_estimation_sigma"])

    def test_car_fallback_when_no_estimation_sigma(self):
        # Non-degenerate variance so the fallback path uses in-window σ(AR)
        ar = pd.DataFrame({"AR": np.linspace(-0.01, 0.02, 10)})
        calc = CumulativeAbnormalReturns()
        out = calc.calculate(ar, windows=[10], estimation_residual_std=None)
        self.assertFalse(out[10]["car_test_uses_estimation_sigma"])
        self.assertTrue(0 <= out[10]["p_value"] <= 1)


if __name__ == "__main__":
    unittest.main()
