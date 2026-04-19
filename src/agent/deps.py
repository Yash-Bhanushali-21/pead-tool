"""
Shared dependencies for PydanticAI research agents.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.analysis.stock_analyzer import StockAnalyzer


@dataclass
class ResearchDeps:
    """Injected into the coordinator agent run."""

    analyzer: StockAnalyzer
    output_base: Path
