"""
PEAD Analyzer
Main orchestrator that coordinates all components of PEAD analysis
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path

from ..data.data_manager import DataManager
from ..documents.pdf_downloader import PDFDownloader
from ..documents.pdf_parser import PDFParser
from ..models.market_model import MarketModel
from ..models.abnormal_returns import AbnormalReturns
from ..models.car import CumulativeAbnormalReturns
from ..scoring.earnings_surprise import EarningsSurpriseScorer
from ..scoring.price_reaction import PriceReactionScorer
from ..scoring.drift_confirmation import DriftConfirmationScorer
from ..scoring.earnings_quality import EarningsQualityScorer
from ..scoring.contextual import ContextualScorer
from ..scoring.composite_score import CompositeScorer
from ..utils.visualization import Visualizer
from ..config.settings import config

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

        logger.info("PEAD Analyzer initialized")

    def analyze_announcement(
        self,
        symbol: str,
        announcement_date: datetime,
        visualize: bool = True,
        output_dir: Optional[str] = None
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
            Directory for outputs

        Returns
        -------
        dict
            Complete analysis results
        """
        logger.info(f"Analyzing {symbol} announcement on {announcement_date}")

        results = {
            'symbol': symbol,
            'announcement_date': announcement_date,
            'timestamp': datetime.now(),
            'success': False,
            'error': None
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

            # 2. Get company fundamentals
            logger.info("Step 2: Fetching company fundamentals")
            company_info = self.data_manager.get_company_fundamentals(symbol)

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
            car_data = car_calculator.calculate(ar_data)
            results['car_data'] = car_data

            # 7. Score all components
            logger.info("Step 7: Calculating component scores")
            scores = self._calculate_all_scores(
                pdf_analysis,
                stock_data,
                market_data,
                car_data,
                company_info,
                announcement_date
            )
            results['scores'] = scores

            # 8. Calculate composite score
            logger.info("Step 8: Computing composite PEAD score")
            composite = self.composite_scorer.calculate_composite_score(
                scores['earnings_surprise'],
                scores['price_reaction'],
                scores['drift_confirmation'],
                scores['earnings_quality'],
                scores['contextual']
            )
            results['composite_score'] = composite

            # 9. Generate visualizations
            if visualize and output_dir:
                logger.info("Step 9: Generating visualizations")
                self._generate_visualizations(
                    symbol, stock_data, announcement_date, ar_data,
                    car_data, composite, output_dir
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

    def analyze_recent_announcements(
        self,
        n: int = 10,
        visualize: bool = True,
        output_dir: str = "./output"
    ) -> pd.DataFrame:
        """
        Analyze top N recent announcements

        Parameters
        ----------
        n : int
            Number of announcements to analyze
        visualize : bool
            Generate visualizations
        output_dir : str
            Output directory

        Returns
        -------
        pd.DataFrame
            Summary of all analyses
        """
        logger.info(f"Analyzing top {n} recent announcements")

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Get recent announcements
        announcements = self.data_manager.get_recent_announcements(n)

        if announcements.empty:
            logger.warning("No announcements found")
            return pd.DataFrame()

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

                # Create symbol-specific output directory
                symbol_dir = output_path / symbol
                symbol_dir.mkdir(exist_ok=True)

                # Perform analysis
                result = self.analyze_announcement(
                    symbol, ann_date, visualize=visualize,
                    output_dir=str(symbol_dir)
                )

                if result['success']:
                    # Extract key metrics for summary
                    summary = self._extract_summary(result)
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
            csv_path = output_path / 'pead_analysis_summary.csv'
            results_df.to_csv(csv_path, index=False)
            logger.info(f"Summary saved to {csv_path}")

            # Generate comparison dashboard
            if visualize:
                dashboard_path = output_path / 'comparison_dashboard.png'
                self.visualizer.plot_comparison_dashboard(
                    results_df, save_path=str(dashboard_path)
                )

            return results_df
        else:
            logger.warning("No successful analyses")
            return pd.DataFrame()

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
        pdf_analysis: Dict,
        stock_data: pd.DataFrame,
        market_data: pd.DataFrame,
        car_data: Dict,
        company_info: Dict,
        announcement_date: datetime
    ) -> Dict:
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
        dict
            All component scores
        """
        scores = {}

        # 1. Earnings Surprise
        earnings_scorer = EarningsSurpriseScorer()
        # Extract financials from PDF metrics
        current_financials = pdf_analysis.get('metrics', {})
        # Use company info as fallback
        current_financials.update(company_info)

        scores['earnings_surprise'] = earnings_scorer.score(
            current_financials,
            {},  # Previous financials (would need historical data)
            pdf_analysis
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

        scores['earnings_quality'] = quality_scorer.score(
            current_financials,
            {},  # Previous financials
            cash_flow_data if isinstance(cash_flow_data, dict) else {}
        )

        # 5. Contextual Factors
        contextual_scorer = ContextualScorer()
        scores['contextual'] = contextual_scorer.score(
            company_info,
            market_data,
            None  # Historical results (would need database)
        )

        return scores

    def _generate_visualizations(
        self,
        symbol: str,
        stock_data: pd.DataFrame,
        announcement_date: datetime,
        ar_data: pd.DataFrame,
        car_data: Dict,
        composite: Dict,
        output_dir: str
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
        if hasattr(ar_data, 'plot'):
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(12, 6))
            ar_data['AR'].plot(ax=ax, title=f'{symbol} - Abnormal Returns')
            ax.axhline(0, color='red', linestyle='--', alpha=0.5)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(output_path / f'{symbol}_ar.png', dpi=300, bbox_inches='tight')
            plt.close()

        # 4. CAR evolution
        from ..models.car import CumulativeAbnormalReturns
        car_obj = CumulativeAbnormalReturns()
        car_obj.cars = car_data
        car_obj.plot_car_evolution(
            save_path=str(output_path / f'{symbol}_car.png')
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

        # Add CAR values
        for window in config.CAR_WINDOWS:
            if window in car_data:
                summary[f'CAR_{window}d'] = car_data[window].get('car_pct', 0)

        return summary
