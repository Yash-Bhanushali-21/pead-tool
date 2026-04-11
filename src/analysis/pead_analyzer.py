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
from src.models.market_model import MarketModel
from src.models.abnormal_returns import AbnormalReturns
from src.models.car import CumulativeAbnormalReturns
from src.scoring.earnings_surprise import EarningsSurpriseScorer
from src.scoring.price_reaction import PriceReactionScorer
from src.scoring.drift_confirmation import DriftConfirmationScorer
from src.scoring.earnings_quality import EarningsQualityScorer
from src.scoring.contextual import ContextualScorer
from src.scoring.composite_score import CompositeScorer
from src.utils.visualization import Visualizer
from src.config.settings import config
from src.fundamentals import FundamentalAnalyzer
from src.technical import TechnicalAnalyzer
from src.synthesis.research_brief import build_research_brief_payload
from src.news import NewsCollector, run_news_sentiment_pipeline
from src.trade_context import compute_trade_context
from src.utils.time_compat import is_instant_after_reference, to_naive_utc_datetime

logger = logging.getLogger(__name__)


def _news_articles_to_json(articles: List) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for a in articles:
        out.append(
            {
                "title": a.title,
                "url": a.url,
                "published": a.published.isoformat() if a.published else None,
                "source": a.source,
                "summary": (a.summary or "")[:2000],
            }
        )
    return out


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
    ) -> Dict:
        """
        Perform complete PEAD analysis for single announcement

        Parameters
        ----------
        symbol : str
            Stock symbol
        announcement_date : datetime
            Announcement date
        visualize : bool
            Whether to generate visualizations
        output_dir : str, optional
            Base output directory; a run subfolder is created under it (see below).
        run_timestamp : str, optional
            If set (e.g. one ID for a batch), used as the datetime prefix so sibling
            runs share the same timestamp.
        include_news : bool
            Fetch Yahoo + Google News RSS and run sentiment (TextBlob + optional OpenAI).
        news_lookback_days : int, optional
            Default from config (90): window ending at *now* for headline scan.
        news_max_articles : int, optional
            Cap on headlines fetched (default from config).

        Each successful run writes under::

            {output_dir}/{ts}_{SYMBOL}_ann{date}_{dataStart}_to_{dataEnd}/

        Returns
        -------
        dict
            Complete analysis results; includes ``output_dir`` (resolved path) when applicable.
        """
        logger.info(f"Analyzing {symbol} announcement on {announcement_date}")

        # Check for future announcement dates (indicates stale cache).
        # Use UTC-normalized ordering—never compare tz-naive vs tz-aware Timestamps.
        if is_instant_after_reference(announcement_date):
            logger.error(
                f"Announcement date {announcement_date} is in the future! "
                f"This indicates stale/corrupted cache. Please clear cache: "
                f"rm -rf data/cache/*"
            )

        announcement_date = to_naive_utc_datetime(announcement_date)

        results = {
            'symbol': symbol,
            'announcement_date': announcement_date,
            'timestamp': datetime.now(),
            'success': False,
            'error': None,
            'output_dir': None,
        }

        try:
            # 1. Fetch data
            logger.info("Step 1: Fetching stock and market data")
            stock_data, market_data = self.data_manager.prepare_analysis_dataset(
                symbol, announcement_date
            )

            if stock_data is None or market_data is None:
                raise ValueError("Insufficient data for analysis")

            results['data_points'] = len(stock_data)

            # Resolve one folder per run: datetime + symbol + ann date + price sample range
            if output_dir:
                from src.utils.run_output import resolve_run_output_directory

                resolved_out = resolve_run_output_directory(
                    output_dir,
                    symbol,
                    announcement_date,
                    stock_data.index,
                    run_timestamp=run_timestamp,
                )
                resolved_out.mkdir(parents=True, exist_ok=True)
                output_dir = str(resolved_out)
                results['output_dir'] = output_dir
                logger.info(f"Run output directory: {output_dir}")

            # 2. Get company fundamentals
            logger.info("Step 2: Fetching company fundamentals")
            company_info = self.data_manager.get_company_fundamentals(symbol)

            # 2b. Fundamental ratio layer (Yahoo) — screening, not a trade signal by itself
            logger.info("Step 2b: Fundamental analysis (ratios & pillars)")
            fundamental_analysis = self.fundamental_analyzer.analyze(symbol, company_info)
            results["fundamental_analysis"] = fundamental_analysis
            if output_dir:
                outp = Path(output_dir)
                outp.mkdir(parents=True, exist_ok=True)
                with open(outp / f"{symbol}_fundamentals.txt", "w", encoding="utf-8") as fh:
                    fh.write(self.fundamental_analyzer.format_report(fundamental_analysis))
                with open(outp / f"{symbol}_fundamentals.json", "w", encoding="utf-8") as fh:
                    fh.write(self.fundamental_analyzer.to_json(fundamental_analysis))
                self.visualizer.plot_fundamental_pillars(
                    fundamental_analysis,
                    save_path=str(outp / f"{symbol}_fundamentals.png"),
                )

            # 3. Download and parse announcement PDF
            logger.info("Step 3: Processing announcement documents")
            pdf_analysis = self._analyze_announcement_pdf(symbol, announcement_date)

            # 4. Estimate market model
            logger.info("Step 4: Estimating market model")
            market_model = MarketModel()
            model_params = market_model.estimate(
                stock_data['Return'],
                market_data['Return'],
                announcement_date
            )
            results['market_model'] = model_params

            # 5. Calculate abnormal returns
            logger.info("Step 5: Calculating abnormal returns")
            ar_calculator = AbnormalReturns(market_model)
            ar_data = ar_calculator.calculate(
                stock_data['Return'],
                market_data['Return'],
                announcement_date,
                event_window=(0, max(config.CAR_WINDOWS)),
                estimate_model=False
            )
            results['abnormal_returns'] = ar_data

            # 6. Calculate CARs
            logger.info("Step 6: Computing CARs for multiple windows")
            car_calculator = CumulativeAbnormalReturns(ar_calculator)
            n_obs = int(model_params.get("n_observations") or 0)
            est_df = max(n_obs - 2, 1)
            car_data = car_calculator.calculate(
                ar_data,
                estimation_residual_std=model_params.get("residual_std"),
                estimation_t_df=est_df,
            )
            results["car_data"] = car_data

            # 7. Score all components
            logger.info("Step 7: Calculating component scores")
            scores, quality_meta = self._calculate_all_scores(
                symbol,
                pdf_analysis,
                stock_data,
                market_data,
                car_data,
                company_info,
                announcement_date,
            )
            results["scores"] = scores

            # 8. Calculate composite score
            logger.info("Step 8: Computing composite PEAD score")
            data_quality: Dict[str, Any] = {
                **quality_meta,
                "r_squared": model_params.get("r_squared"),
                "residual_std": model_params.get("residual_std"),
                "n_observations": model_params.get("n_observations"),
            }
            composite = self.composite_scorer.calculate_composite_score(
                scores["earnings_surprise"],
                scores["price_reaction"],
                scores["drift_confirmation"],
                scores["earnings_quality"],
                scores["contextual"],
                data_quality=data_quality,
            )
            results['composite_score'] = composite

            # 9. Technical indicators (same price sample)
            logger.info("Step 9: Technical analysis (RSI, MACD, MAs, ATR%)")
            technical_analysis = self.technical_analyzer.analyze(
                stock_data,
                pd.Timestamp(announcement_date),
                symbol=symbol,
            )
            results["technical_analysis"] = technical_analysis
            if output_dir:
                outp = Path(output_dir)
                with open(outp / f"{symbol}_technical.json", "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(technical_analysis, indent=2, default=str))

            # 10. News scan + sentiment (headlines/snippets; lookback ends at now)
            results["news_sentiment"] = None
            if include_news:
                logger.info("Step 10: News collection & sentiment (RSS + Yahoo)")
                results["news_sentiment"] = {
                    "article_count": 0,
                    "news_score_0_100": 50.0,
                    "method": "none",
                    "openai_used": False,
                }
                try:
                    lb = (
                        news_lookback_days
                        if news_lookback_days is not None
                        else config.NEWS_LOOKBACK_DAYS
                    )
                    company_name = (company_info.get("company_name") or symbol).strip()
                    coll = NewsCollector()
                    _max_art = (
                        int(news_max_articles)
                        if news_max_articles is not None
                        else config.NEWS_MAX_ARTICLES
                    )
                    articles = coll.collect(
                        symbol,
                        company_name,
                        datetime.now(),
                        lookback_days=int(lb),
                        max_articles=_max_art,
                    )
                    ns = run_news_sentiment_pipeline(symbol, company_name, articles)
                    results["news_sentiment"] = ns
                    if output_dir:
                        outp = Path(output_dir)
                        with open(
                            outp / f"{symbol}_news_articles.json",
                            "w",
                            encoding="utf-8",
                        ) as fh:
                            fh.write(
                                json.dumps(
                                    _news_articles_to_json(articles),
                                    indent=2,
                                    ensure_ascii=False,
                                )
                            )
                        with open(
                            outp / f"{symbol}_news_sentiment.json",
                            "w",
                            encoding="utf-8",
                        ) as fh:
                            fh.write(json.dumps(ns, indent=2, default=str))
                except Exception as e:
                    logger.warning("News pipeline failed: %s", e)
                    results["news_sentiment"]["error"] = str(e)

            # 10b. Trade execution context (liquidity, vol regime, alignment, model fit)
            logger.info("Step 10b: Trade readiness / execution context")
            try:
                results["trade_context"] = compute_trade_context(results, stock_data)
            except Exception as e:
                logger.warning("Trade context failed: %s", e)
                results["trade_context"] = {"error": str(e), "trade_readiness_score_0_100": None}

            # 11. Unified research brief (PEAD + fundamentals + technical + news + trade context)
            logger.info("Step 11: Research brief (synthesis)")
            _brief_payload = build_research_brief_payload(results)
            results["research_brief"] = _brief_payload["text"]
            results["synthesis"] = {
                k: v for k, v in _brief_payload.items() if k != "text"
            }
            if output_dir:
                outp = Path(output_dir)
                with open(outp / f"{symbol}_research_brief.txt", "w", encoding="utf-8") as fh:
                    fh.write(results["research_brief"])
                with open(outp / f"{symbol}_synthesis.json", "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(results["synthesis"], indent=2, default=str))

            # 12. Generate visualizations
            if visualize and output_dir:
                logger.info("Step 12: Generating visualizations")
                self._generate_visualizations(
                    symbol,
                    stock_data,
                    announcement_date,
                    ar_data,
                    car_data,
                    composite,
                    output_dir,
                    technical_analysis=technical_analysis,
                )

            results['success'] = True
            logger.info(
                f"Analysis complete for {symbol}. "
                f"Composite Score: {composite['composite_score']:.2f}/100 "
                f"({composite['rating']})"
            )

        except Exception as e:
            logger.error(f"Analysis failed for {symbol}: {e}", exc_info=True)
            results['error'] = str(e)

        return results

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
        results: Dict[str, Any] = {
            "symbol": symbol,
            "announcement_date": announcement_date,
            "success": False,
            "error": None,
            "mode": "scoring_only",
        }
        try:
            announcement_date = to_naive_utc_datetime(announcement_date)
            if is_instant_after_reference(announcement_date):
                results["error"] = (
                    "Announcement date is in the future — likely stale cache. "
                    "Try clearing data/cache or pass an explicit past date."
                )
                return results

            logger.info("Scoring-only: fetching OHLCV / index")
            stock_data, market_data = self.data_manager.prepare_analysis_dataset(
                symbol, announcement_date
            )
            if stock_data is None or market_data is None:
                results["error"] = "Insufficient data for analysis"
                return results

            results["data_points"] = int(len(stock_data))

            company_info = self.data_manager.get_company_fundamentals(symbol)

            logger.info("Scoring-only: announcement PDF")
            pdf_analysis = self._analyze_announcement_pdf(symbol, announcement_date)
            results["pdf_analysis_meta"] = {
                "text_chars": len((pdf_analysis.get("text") or "")),
                "metric_keys": list((pdf_analysis.get("metrics") or {}).keys())
                if isinstance(pdf_analysis.get("metrics"), dict)
                else [],
                "has_guidance": bool((pdf_analysis.get("guidance") or {}).get("has_guidance")),
            }

            logger.info("Scoring-only: market model")
            market_model = MarketModel()
            model_params = market_model.estimate(
                stock_data["Return"],
                market_data["Return"],
                announcement_date,
            )
            results["market_model"] = model_params

            logger.info("Scoring-only: abnormal returns / CAR")
            ar_calculator = AbnormalReturns(market_model)
            ar_data = ar_calculator.calculate(
                stock_data["Return"],
                market_data["Return"],
                announcement_date,
                event_window=(0, max(config.CAR_WINDOWS)),
                estimate_model=False,
            )
            ar_summary: Dict[str, Any] = {"rows": 0, "tail": []}
            if isinstance(ar_data, pd.DataFrame) and not ar_data.empty and "AR" in ar_data.columns:
                ar_summary["rows"] = int(len(ar_data))
                tail = ar_data.tail(8)
                ar_summary["tail"] = tail.reset_index().to_dict(orient="records")
            results["abnormal_returns_summary"] = ar_summary

            car_calculator = CumulativeAbnormalReturns(ar_calculator)
            n_obs = int(model_params.get("n_observations") or 0)
            est_df = max(n_obs - 2, 1)
            car_data = car_calculator.calculate(
                ar_data,
                estimation_residual_std=model_params.get("residual_std"),
                estimation_t_df=est_df,
            )
            results["car_data"] = car_data

            scores, quality_meta = self._calculate_all_scores(
                symbol,
                pdf_analysis,
                stock_data,
                market_data,
                car_data,
                company_info,
                announcement_date,
            )
            results["scores"] = scores

            data_quality: Dict[str, Any] = {
                **quality_meta,
                "r_squared": model_params.get("r_squared"),
                "residual_std": model_params.get("residual_std"),
                "n_observations": model_params.get("n_observations"),
            }
            composite = self.composite_scorer.calculate_composite_score(
                scores["earnings_surprise"],
                scores["price_reaction"],
                scores["drift_confirmation"],
                scores["earnings_quality"],
                scores["contextual"],
                data_quality=data_quality,
            )
            results["composite_score"] = composite
            results["success"] = True
        except Exception as e:
            logger.error("Scoring-only failed for %s: %s", symbol, e, exc_info=True)
            results["error"] = str(e)

        return results

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

            # Sort by composite score
            results_df = results_df.sort_values('Composite_Score', ascending=False)

            # Save to CSV
            csv_path = batch_parent / 'pead_analysis_summary.csv'
            results_df.to_csv(csv_path, index=False)
            logger.info(f"Summary saved to {csv_path}")

            # Generate comparison dashboard
            if visualize:
                dashboard_path = batch_parent / 'comparison_dashboard.png'
                self.visualizer.plot_comparison_dashboard(
                    results_df, save_path=str(dashboard_path)
                )

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

    def _generate_visualizations(
        self,
        symbol: str,
        stock_data: pd.DataFrame,
        announcement_date: datetime,
        ar_data: pd.DataFrame,
        car_data: Dict,
        composite: Dict,
        output_dir: str,
        technical_analysis: Optional[Dict] = None,
    ):
        """
        Generate all visualizations

        Parameters
        ----------
        symbol : str
            Stock symbol
        stock_data : pd.DataFrame
            Stock data
        announcement_date : datetime
            Announcement date
        ar_data : pd.DataFrame
            Abnormal returns data
        car_data : dict
            CAR data
        composite : dict
            Composite score data
        output_dir : str
            Output directory
        """
        output_path = Path(output_dir)

        # 1. Price and announcement
        self.visualizer.plot_price_and_announcement(
            stock_data,
            pd.Timestamp(announcement_date),
            save_path=str(output_path / f'{symbol}_price.png')
        )

        # 2. Score components
        self.visualizer.plot_score_components(
            composite,
            save_path=str(output_path / f'{symbol}_scores.png')
        )

        # 3. AR plot
        if isinstance(ar_data, pd.DataFrame) and not ar_data.empty and 'AR' in ar_data.columns:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(12, 6))
            ar_data['AR'].plot(ax=ax, title=f'{symbol} - Abnormal Returns')
            ax.axhline(0, color='red', linestyle='--', alpha=0.5)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(output_path / f'{symbol}_ar.png', dpi=300, bbox_inches='tight')
            plt.close()
            logger.info(f"Plot saved to {output_path / f'{symbol}_ar.png'}")
        else:
            logger.warning(f"Skipping AR plot - no abnormal returns data available")

        # 4. CAR evolution
        if car_data and len(car_data) > 0:
            from src.models.car import CumulativeAbnormalReturns
            car_obj = CumulativeAbnormalReturns()
            car_obj.cars = car_data
            car_obj.plot_car_evolution(
                save_path=str(output_path / f'{symbol}_car.png')
            )
        else:
            logger.warning(f"Skipping CAR plot - no CAR data available")

        if technical_analysis:
            self.visualizer.plot_technical_panel(
                stock_data,
                pd.Timestamp(announcement_date),
                technical_analysis,
                save_path=str(output_path / f"{symbol}_technical.png"),
            )

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
        composite = result.get('composite_score', {})
        components = composite.get('components', {})
        car_data = result.get('car_data', {})

        summary = {
            'Symbol': result['symbol'],
            'Announcement_Date': result['announcement_date'],
            'Composite_Score': composite.get('composite_score', 0),
            'Rating': composite.get('rating', 'N/A'),
            'Confidence': composite.get('confidence', 0),
            'Earnings_Surprise': components.get('earnings_surprise', 0),
            'Price_Reaction': components.get('price_reaction', 0),
            'Drift_Confirmation': components.get('drift_confirmation', 0),
            'Earnings_Quality': components.get('earnings_quality', 0),
            'Contextual': components.get('contextual', 0),
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

        # Add CAR values
        for window in config.CAR_WINDOWS:
            if window in car_data:
                summary[f"CAR_{window}d"] = car_data[window].get("car", 0)

        return summary
