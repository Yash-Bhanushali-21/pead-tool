"""
PEAD Analyzer
Main orchestrator that coordinates all components of PEAD analysis
"""
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from pathlib import Path

from src.data.data_manager import DataManager
from src.documents.pdf_downloader import PDFDownloader
from src.documents.pdf_parser import PDFParser
from src.scoring.earnings_surprise import EarningsSurpriseScorer
from src.scoring.price_reaction import PriceReactionScorer
from src.scoring.drift_confirmation import DriftConfirmationScorer
from src.scoring.earnings_quality import EarningsQualityScorer
from src.scoring.contextual import ContextualScorer
from src.scoring.composite_score import CompositeScorer
from src.utils.visualization import Visualizer
from src.config.config import config
from src.fundamentals import FundamentalAnalyzer
from src.technical import TechnicalAnalyzer
from src.utils.time_compat import is_instant_after_reference, to_naive_utc_datetime
from src.equity_research_pipeline.full_run_steps import select_equity_research_stages
from src.equity_research_pipeline.logging_utils import equity_research_log_adapter
from src.equity_research_pipeline.options import EquityResearchRunOptions
from src.equity_research_pipeline.context import new_equity_run_context
from src.equity_research_pipeline.runner import execute_pipeline
from src.equity_research_pipeline.scoring_steps import SCORING_ONLY_STEPS, new_scoring_context

logger = logging.getLogger(__name__)


class PEADAnalyzer:
    """
    Main PEAD analysis orchestrator

    Coordinates data fetching, modeling, scoring, and reporting
    """

    def __init__(self, use_cache: bool = True):
        """
        Initialize PEAD analyzer

        Parameters
        ----------
        use_cache : bool
            Whether to use cached data
        """
        # Initialize components
        self.data_manager = DataManager(use_cache=use_cache)
        self.pdf_downloader = PDFDownloader()
        self.pdf_parser = PDFParser()
        self.composite_scorer = CompositeScorer()
        self.visualizer = Visualizer()
        self.fundamental_analyzer = FundamentalAnalyzer()
        self.technical_analyzer = TechnicalAnalyzer()

        logger.info("PEAD Analyzer initialized")

    def analyze_announcement(
        self,
        symbol: str,
        announcement_date: datetime,
        visualize: bool = True,
        output_dir: Optional[str] = None,
        run_timestamp: Optional[str] = None,
        include_news: bool = True,
        news_lookback_days: Optional[int] = None,
        news_max_articles: Optional[int] = None,
        include_desk_insight: bool = True,
        include_market_sentiment: bool = True,
        market_sentiment_max_articles: int = 40,
        include_symbol_news_ai_digest: bool = True,
        include_market_news_ai_digest: bool = True,
    ) -> Dict:
        """
        Back-compat: expand a single event anchor to the legacy PEAD calendar window and run
        :meth:`analyze_equity_research` on that span.
        """
        ann = to_naive_utc_datetime(announcement_date)
        start, end = DataManager.event_window_fetch_bounds(ann)
        return self.analyze_equity_research(
            symbol,
            start,
            end,
            visualize=visualize,
            output_dir=output_dir,
            run_timestamp=run_timestamp,
            include_news=include_news,
            news_lookback_days=news_lookback_days,
            news_max_articles=news_max_articles,
            include_desk_insight=include_desk_insight,
            include_market_sentiment=include_market_sentiment,
            market_sentiment_max_articles=market_sentiment_max_articles,
            include_symbol_news_ai_digest=include_symbol_news_ai_digest,
            include_market_news_ai_digest=include_market_news_ai_digest,
        )

    def analyze_equity_research(
        self,
        symbol: str,
        analysis_start: datetime,
        analysis_end: datetime,
        visualize: bool = True,
        output_dir: Optional[str] = None,
        run_timestamp: Optional[str] = None,
        include_news: bool = True,
        news_lookback_days: Optional[int] = None,
        news_max_articles: Optional[int] = None,
        include_desk_insight: bool = True,
        include_market_sentiment: bool = True,
        market_sentiment_max_articles: int = 40,
        include_symbol_news_ai_digest: bool = True,
        include_market_news_ai_digest: bool = True,
        pipeline_stages: Optional[Tuple[str, ...]] = None,
    ) -> Dict:
        """
        Equity research for one symbol over an explicit inclusive calendar window ``[start, end]``.

        One OHLCV fetch drives technical (via preloaded frame) and trade context; news uses the
        same window. Fundamentals remain a company snapshot (not day-by-day over the range).

        Parameters
        ----------
        symbol : str
            NSE symbol
        analysis_start, analysis_end : datetime
            Inclusive window for OHLCV, technical, news, and trade-context price input
        visualize : bool
            When ``output_dir`` is set, write the fundamentals pillar PNG (``*_fundamentals.png``).
        output_dir : str, optional
            Base output directory; a run subfolder is created under it
        run_timestamp : str, optional
            Batch runs: shared timestamp prefix for sibling folders
        include_news : bool
            When True, runs ``run_news_sentiment_layer`` with the same calendar window
        news_lookback_days, news_max_articles : optional
            Caps for news layer (window is fixed by ``analysis_*``)
        include_desk_insight : bool
            When True, runs the research-desk LLM step on the consolidated bundle (requires API key).
        include_market_sentiment : bool
            When True, runs broader India/market headline pass (same window) below symbol-scoped news.
        market_sentiment_max_articles : int
            Cap for the market-sentiment collector merge.
        include_symbol_news_ai_digest, include_market_news_ai_digest : bool
            When False, skips the final OpenAI ``ai_digest`` narrative for that pass (lexicon + optional headline synthesis unchanged).
        pipeline_stages : tuple of str, optional
            Run only these pipeline stage ids (see ``EQUITY_PIPELINE_STAGE_IDS`` / tools API).
            ``None`` runs the full pipeline. OHLCV fetch is auto-inserted when required.

        Returns
        -------
        dict
            ``fundamental_analysis``, ``technical_analysis`` / ``technical_tool_response``,
            ``news_sentiment`` / ``news_tool_response``, ``market_sentiment`` / ``market_tool_response``,
            ``trade_context``, ``research_desk``, ``pipeline_trace``.
        """
        a0 = to_naive_utc_datetime(analysis_start)
        a1 = to_naive_utc_datetime(analysis_end)
        logger.info("Equity research run: %s %s .. %s", symbol, a0, a1)

        if is_instant_after_reference(a1):
            logger.error(
                "analysis_end %s is in the future — likely bad input or clock skew.",
                a1,
            )

        opts = EquityResearchRunOptions(
            visualize=visualize,
            output_dir=output_dir,
            run_timestamp=run_timestamp,
            include_news=include_news,
            news_lookback_days=news_lookback_days,
            news_max_articles=news_max_articles,
            include_desk_insight=include_desk_insight,
            include_market_sentiment=include_market_sentiment,
            market_sentiment_max_articles=int(market_sentiment_max_articles),
            include_symbol_news_ai_digest=bool(include_symbol_news_ai_digest),
            include_market_news_ai_digest=bool(include_market_news_ai_digest),
            pipeline_stages=tuple(pipeline_stages) if pipeline_stages is not None else None,
        )
        ctx = new_equity_run_context(symbol, a0, a1, opts)
        rlog = equity_research_log_adapter(logger, run_id=ctx.run_id, symbol=ctx.symbol)

        try:
            stages = select_equity_research_stages(opts)
            ctx.results["equity_pipeline_stages"] = [n for n, _ in stages]
            execute_pipeline(ctx, self, stages, rlog)
            ctx.results["success"] = True
            logger.info("Equity research run finished for %s", symbol)
        except Exception as e:
            logger.error("Analysis failed for %s: %s", symbol, e, exc_info=True)
            ctx.results["error"] = str(e)

        return ctx.results

    def analyze_scoring_only(
        self,
        symbol: str,
        announcement_date: datetime,
    ) -> Dict[str, Any]:
        """
        Event study + PEAD component scores + composite only.

        Skips fundamental screening files, technicals, news, trade context, synthesis,
        visualizations, and on-disk artifacts — for isolated scoring tests.
        """
        symbol = symbol.strip().upper()
        announcement_date = to_naive_utc_datetime(announcement_date)
        if is_instant_after_reference(announcement_date):
            return {
                "symbol": symbol,
                "announcement_date": announcement_date,
                "success": False,
                "error": (
                    "Announcement date is in the future — likely stale cache. "
                    "Try clearing data/cache or pass an explicit past date."
                ),
                "mode": "scoring_only",
            }

        logger.info("Scoring-only: fetching OHLCV / index")
        stock_data, market_data = self.data_manager.prepare_analysis_dataset(
            symbol, announcement_date
        )
        if stock_data is None or market_data is None:
            return {
                "symbol": symbol,
                "announcement_date": announcement_date,
                "success": False,
                "error": "Insufficient data for analysis",
                "mode": "scoring_only",
            }

        ctx = new_scoring_context(symbol, announcement_date)
        ctx.announcement_date = announcement_date
        ctx.results["announcement_date"] = announcement_date
        ctx.workspace["stock_data"] = stock_data
        ctx.workspace["market_data"] = market_data
        ctx.results["data_points"] = int(len(stock_data))

        rlog = equity_research_log_adapter(logger, run_id=ctx.run_id, symbol=ctx.symbol)
        try:
            execute_pipeline(ctx, self, SCORING_ONLY_STEPS, rlog, trace_key="scoring_pipeline_trace")
            ctx.results["success"] = True
        except Exception as e:
            logger.error("Scoring-only failed for %s: %s", symbol, e, exc_info=True)
            ctx.results["error"] = str(e)

        return ctx.results

    def analyze_recent_announcements(
        self,
        n: int = 10,
        visualize: bool = True,
        output_dir: str = "./output",
        include_news: bool = True,
        news_lookback_days: Optional[int] = None,
        news_max_articles: Optional[int] = None,
    ) -> Tuple[pd.DataFrame, Optional[Path]]:
        """
        Analyze top N recent announcements

        Parameters
        ----------
        n : int
            Number of announcements to analyze
        visualize : bool
            Generate visualizations
        output_dir : str
            Base output directory. A batch folder is created, then one subfolder per symbol.

        Returns
        -------
        tuple
            (summary DataFrame, batch root Path or None)
        """
        logger.info(f"Analyzing top {n} recent announcements")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Get recent announcements
        announcements = self.data_manager.get_recent_announcements(n)

        if announcements.empty:
            logger.warning("No announcements found")
            return pd.DataFrame(), None

        batch_ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        batch_parent = output_path / f"{batch_ts}_RECENT_top{n}"
        batch_parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Batch output root: {batch_parent}")

        logger.info(f"Found {len(announcements)} announcements")

        # Analyze each announcement
        results_list = []

        for idx, row in announcements.iterrows():
            try:
                symbol = row.get('SYMBOL', '')
                ann_date = row.get('ANNOUNCEMENT_DATE', datetime.now())

                logger.info(f"\n{'='*60}")
                logger.info(f"Analyzing {idx+1}/{len(announcements)}: {symbol}")
                logger.info(f"{'='*60}")

                # Perform analysis (nested run folder under batch_parent)
                result = self.analyze_announcement(
                    symbol,
                    ann_date,
                    visualize=visualize,
                    output_dir=str(batch_parent),
                    run_timestamp=batch_ts,
                    include_news=include_news,
                    news_lookback_days=news_lookback_days,
                    news_max_articles=news_max_articles,
                )

                if result['success']:
                    # Extract key metrics for summary
                    summary = self._extract_summary(result)
                    summary["Run_Output_Dir"] = result.get("output_dir")
                    results_list.append(summary)

            except Exception as e:
                logger.error(f"Failed to analyze {symbol}: {e}")
                continue

        # Create summary DataFrame
        if results_list:
            results_df = pd.DataFrame(results_list)

            if results_df["Composite_Score"].notna().any():
                results_df = results_df.sort_values("Composite_Score", ascending=False)
            elif "Fundamental_Score" in results_df.columns and results_df["Fundamental_Score"].notna().any():
                results_df = results_df.sort_values("Fundamental_Score", ascending=False)
            elif "Technical_Score" in results_df.columns and results_df["Technical_Score"].notna().any():
                results_df = results_df.sort_values("Technical_Score", ascending=False)

            # Save to CSV
            csv_path = batch_parent / 'pead_analysis_summary.csv'
            results_df.to_csv(csv_path, index=False)
            logger.info(f"Summary saved to {csv_path}")

            if visualize and results_df["Composite_Score"].notna().any():
                dashboard_path = batch_parent / 'comparison_dashboard.png'
                self.visualizer.plot_comparison_dashboard(
                    results_df, save_path=str(dashboard_path)
                )
            elif visualize:
                logger.info("Skipping PEAD comparison dashboard — no composite scores in this batch")

            return results_df, batch_parent
        else:
            logger.warning("No successful analyses")
            return pd.DataFrame(), batch_parent

    def _analyze_announcement_pdf(
        self,
        symbol: str,
        announcement_date: datetime
    ) -> Dict:
        """
        Download and analyze announcement PDF

        Parameters
        ----------
        symbol : str
            Stock symbol
        announcement_date : datetime
            Announcement date

        Returns
        -------
        dict
            PDF analysis results
        """
        # Check if PDF exists or try to download
        pdf_path = self.pdf_downloader.get_pdf_path(symbol, announcement_date)

        if pdf_path and pdf_path.exists():
            logger.info(f"Parsing PDF for {symbol}")
            analysis = self.pdf_parser.parse_announcement(pdf_path)

            # Add guidance analysis
            if analysis['text']:
                guidance = self.pdf_parser.extract_guidance(analysis['text'])
                analysis['guidance'] = guidance

            return analysis
        else:
            logger.warning(f"No PDF found for {symbol}")
            return {
                'text': '',
                'metrics': {},
                'sentiment': {'sentiment_score': 0},
                'guidance': {'has_guidance': False}
            }

    def _calculate_all_scores(
        self,
        symbol: str,
        pdf_analysis: Dict,
        stock_data: pd.DataFrame,
        market_data: pd.DataFrame,
        car_data: Dict,
        company_info: Dict,
        announcement_date: datetime,
    ) -> Tuple[Dict, Dict[str, Any]]:
        """
        Calculate all scoring components

        Parameters
        ----------
        pdf_analysis : dict
            PDF analysis results
        stock_data : pd.DataFrame
            Stock data
        market_data : pd.DataFrame
            Market data
        car_data : dict
            CAR data
        company_info : dict
            Company fundamentals
        announcement_date : datetime
            Announcement date

        Returns
        -------
        tuple
            (scores dict, quality_meta dict for composite confidence)
        """
        scores: Dict[str, Any] = {}

        yahoo_cur, yahoo_yoy = self.data_manager.yahoo_fetcher.get_yoy_quarter_metrics(symbol)
        has_yahoo_yoy = bool(yahoo_cur) and bool(yahoo_yoy)

        # 1. Earnings Surprise
        earnings_scorer = EarningsSurpriseScorer()
        current_financials: Dict[str, Any] = {}
        previous_financials: Dict[str, Any] = {}
        if has_yahoo_yoy:
            for key in ("revenue", "eps", "operating_margin", "ebitda", "net_margin"):
                if yahoo_cur.get(key) is not None:
                    current_financials[key] = yahoo_cur[key]
                if yahoo_yoy.get(key) is not None:
                    previous_financials[key] = yahoo_yoy[key]
        for k, v in company_info.items():
            if k == "financials":
                continue
            current_financials.setdefault(k, v)
        # Parsed PDF tables override Yahoo when present
        current_financials.update(pdf_analysis.get("metrics") or {})

        scores["earnings_surprise"] = earnings_scorer.score(
            current_financials,
            previous_financials,
            pdf_analysis,
        )

        # Get earnings direction for other scorers
        earnings_direction = np.sign(scores['earnings_surprise']['total'])

        # 2. Price Reaction
        price_scorer = PriceReactionScorer()
        scores['price_reaction'] = price_scorer.score(
            stock_data,
            pd.Timestamp(announcement_date),
            earnings_direction
        )

        # 3. Drift Confirmation
        drift_scorer = DriftConfirmationScorer()
        scores['drift_confirmation'] = drift_scorer.score(
            car_data,
            stock_data,
            market_data,
            pd.Timestamp(announcement_date)
        )

        # 4. Earnings Quality
        quality_scorer = EarningsQualityScorer()
        cash_flow_data = company_info.get('financials', {}).get('cash_flow', {})

        scores["earnings_quality"] = quality_scorer.score(
            current_financials,
            previous_financials,
            cash_flow_data if isinstance(cash_flow_data, dict) else {},
        )

        # 5. Contextual Factors
        contextual_scorer = ContextualScorer()
        scores["contextual"] = contextual_scorer.score(
            company_info,
            market_data,
            None,  # Historical results (would need database)
        )

        quality_meta = {
            "has_pdf_text": bool((pdf_analysis.get("text") or "").strip()),
            "has_yahoo_yoy": has_yahoo_yoy,
        }
        return scores, quality_meta

    def _extract_summary(self, result: Dict) -> Dict:
        """
        Extract summary metrics from full result

        Parameters
        ----------
        result : dict
            Full analysis result

        Returns
        -------
        dict
            Summary metrics
        """
        composite = result.get("composite_score") or {}
        components = composite.get("components") or {} if isinstance(composite, dict) else {}
        car_data = result.get("car_data") or {}

        summary = {
            "Symbol": result["symbol"],
            "Announcement_Date": result["announcement_date"],
            "Composite_Score": composite.get("composite_score") if composite else None,
            "Rating": composite.get("rating") if composite else None,
            "Confidence": composite.get("confidence") if composite else None,
            "Earnings_Surprise": components.get("earnings_surprise"),
            "Price_Reaction": components.get("price_reaction"),
            "Drift_Confirmation": components.get("drift_confirmation"),
            "Earnings_Quality": components.get("earnings_quality"),
            "Contextual": components.get("contextual"),
        }
        fa = result.get("fundamental_analysis") or {}
        fscores = fa.get("scores") or {}
        summary["Fundamental_Score"] = fscores.get("fundamental_score", None)
        summary["Fundamental_Stance"] = fa.get("stance", "")
        summary["Run_Output_Dir"] = result.get("output_dir")
        syn = result.get("synthesis") or {}
        summary["Synthesis_Blend"] = syn.get("blend_score")
        summary["Synthesis_Bias"] = syn.get("bias_label")
        summary["Technical_Score"] = (result.get("technical_analysis") or {}).get("scores", {}).get(
            "technical_score"
        )
        ns = result.get("news_sentiment") or {}
        summary["News_Score"] = ns.get("news_score_0_100")
        summary["News_Articles"] = ns.get("article_count")
        tcx = result.get("trade_context") or {}
        summary["Trade_Readiness"] = tcx.get("trade_readiness_score_0_100")

        for window in config.CAR_WINDOWS:
            if isinstance(car_data, dict) and window in car_data:
                summary[f"CAR_{window}d"] = car_data[window].get("car", 0)

        return summary
