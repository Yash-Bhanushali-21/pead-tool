"""Timezone normalization for PEAD anchors."""
import datetime
import unittest

import pandas as pd

from src.utils.time_compat import (
    is_instant_after_reference,
    to_calendar_date,
    to_naive_utc_datetime,
)


class TestTimeCompat(unittest.TestCase):
    def test_naive_roundtrip(self):
        d = datetime.datetime(2024, 6, 15, 12, 0, 0)
        out = to_naive_utc_datetime(d)
        self.assertIsNone(out.tzinfo)
        self.assertEqual(out.year, 2024)
        self.assertEqual(out.month, 6)
        self.assertEqual(out.day, 15)

    def test_aware_utc_strips_to_naive_utc_wall(self):
        ts = pd.Timestamp("2024-01-10 18:30:00", tz="Asia/Kolkata")
        out = to_naive_utc_datetime(ts)
        self.assertIsNone(out.tzinfo)
        self.assertEqual(out.hour, 13)
        self.assertEqual(out.minute, 0)

    def test_future_check_no_typeerror_tz_aware(self):
        past = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)
        self.assertFalse(is_instant_after_reference(past))
        future = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=365)
        self.assertTrue(is_instant_after_reference(future))

    def test_to_calendar_date(self):
        import datetime as dt

        d = dt.date(2024, 3, 1)
        self.assertEqual(to_calendar_date(d), d)
        self.assertEqual(to_calendar_date(dt.datetime(2024, 3, 1, 15, 0, 0)), d)


if __name__ == "__main__":
    unittest.main()
