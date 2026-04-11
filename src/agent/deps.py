"""
Shared dependencies for PydanticAI research agents.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.analysis.pead_analyzer import PEADAnalyzer


@dataclass
class ResearchDeps:
    """Injected into the coordinator agent run."""

    analyzer: PEADAnalyzer
    output_base: Path
