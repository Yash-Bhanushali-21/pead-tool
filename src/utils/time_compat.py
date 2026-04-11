"""
Timezone-safe datetime handling for PEAD anchors and comparisons.

Pandas forbids comparing tz-naive and tz-aware timestamps. External feeds (Yahoo,
NSE-derived series) may yield timezone-aware instants while local ``datetime.now()``
is often naive—normalize before any ordering or alignment.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Union

import pandas as pd

TimestampLike = Union[datetime, pd.Timestamp, str, float, int]


def to_calendar_date(value: Union[datetime, date, pd.Timestamp]) -> date:
    """
    Calendar date for vendor APIs (NSE historical endpoints require ``datetime.date``;
    yfinance accepts ``date`` for ``history(start=..., end=...)``).
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def to_naive_utc_datetime(value: TimestampLike) -> datetime:
    """
    Convert any pandas-parsable instant to a **timezone-naive** ``datetime``
    whose wall clock equals that instant in **UTC**.

    Date-only strings (e.g. ``\"2024-01-15\"``) parse as midnight UTC-naive,
    consistent with calendar-style anchors used in event studies.
    """
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()


def is_instant_after_reference(
    event: TimestampLike,
    reference: TimestampLike | None = None,
) -> bool:
    """
    Chronological ordering in UTC: ``event > reference``.

    ``reference`` defaults to "now" in UTC. Comparisons use naive UTC
    :class:`~datetime.datetime` only—never mixed pandas tz-aware vs naive.
    """
    ev = to_naive_utc_datetime(event)
    if reference is None:
        ref = to_naive_utc_datetime(pd.Timestamp.now(tz="UTC"))
    else:
        ref = to_naive_utc_datetime(reference)
    return ev > ref
