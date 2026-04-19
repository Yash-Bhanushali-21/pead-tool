"""Run-scoped logging extras for equity research pipeline stages."""

from __future__ import annotations

import logging
from typing import Any


def equity_research_log_adapter(
    base: logging.Logger,
    *,
    run_id: str,
    symbol: str,
) -> logging.LoggerAdapter:
    """
    Wrap ``base`` so every line carries ``equity_run_id`` and ``equity_symbol``.

    Formatter example::
        %(levelname)s [%(equity_run_id)s %(equity_symbol)s] %(name)s: %(message)s
    """

    class _Adapter(logging.LoggerAdapter):
        def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
            extra = dict(kwargs.get("extra") or {})
            extra.setdefault("equity_run_id", self.extra.get("equity_run_id", ""))
            extra.setdefault("equity_symbol", self.extra.get("equity_symbol", ""))
            kwargs["extra"] = extra
            return msg, kwargs

    return _Adapter(base, {"equity_run_id": run_id, "equity_symbol": symbol})
