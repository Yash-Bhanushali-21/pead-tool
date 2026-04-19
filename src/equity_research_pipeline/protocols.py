"""Structural typing for pipeline stages (``PEADAnalyzer`` satisfies this protocol)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Protocol, Tuple

import pandas as pd

from src.data.data_manager import DataManager
from src.documents.pdf_downloader import PDFDownloader
from src.documents.pdf_parser import PDFParser
from src.fundamentals import FundamentalAnalyzer
from src.scoring.composite_score import CompositeScorer
from src.technical import TechnicalAnalyzer
from src.utils.visualization import Visualizer


class EquityResearchAnalyzerServices(Protocol):
    """Subset of ``PEADAnalyzer`` used by scoring-only PEAD stages and shared services."""

    data_manager: DataManager
    pdf_downloader: PDFDownloader
    pdf_parser: PDFParser
    composite_scorer: CompositeScorer
    visualizer: Visualizer
    fundamental_analyzer: FundamentalAnalyzer
    technical_analyzer: TechnicalAnalyzer

    def _analyze_announcement_pdf(self, symbol: str, announcement_date: datetime) -> Dict[str, Any]:
        ...

    def _calculate_all_scores(
        self,
        symbol: str,
        pdf_analysis: Dict[str, Any],
        stock_data: pd.DataFrame,
        market_data: pd.DataFrame,
        car_data: Dict[str, Any],
        company_info: Dict[str, Any],
        announcement_date: datetime,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        ...
