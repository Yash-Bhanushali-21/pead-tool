#!/usr/bin/env python3
"""
PEAD Tool - Main Entry Point
Post-Earnings Announcement Drift Analysis for Indian Equity Markets

Usage:
    python main.py --mode recent --top 10
    python main.py --mode single --symbol RELIANCE --date 2024-01-15
    python main.py --mode batch --file stocks.csv
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.analysis.pead_analyzer import PEADAnalyzer
from src.config.settings import config


def setup_logging(verbose: bool = False):
    """
    Setup logging configuration

    Parameters
    ----------
    verbose : bool
        Enable verbose logging
    """
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('pead_analysis.log')
        ]
    )

    # Reduce noise from third-party libraries
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def analyze_recent(args):
    """
    Analyze recent announcements

    Parameters
    ----------
    args : argparse.Namespace
        Command line arguments
    """
    print("\n" + "="*70)
    print("PEAD TOOL - Analyzing Recent Announcements")
    print("="*70 + "\n")

    analyzer = PEADAnalyzer(use_cache=not args.no_cache)

    results = analyzer.analyze_recent_announcements(
        n=args.top,
        visualize=args.visualize,
        output_dir=args.output
    )

    if not results.empty:
        print("\n" + "="*70)
        print("ANALYSIS SUMMARY")
        print("="*70 + "\n")
        print(results.to_string())
        print("\n")

        # Print top opportunities
        print("="*70)
        print("TOP OPPORTUNITIES")
        print("="*70 + "\n")

        top_opportunities = results.head(5)
        for idx, row in top_opportunities.iterrows():
            print(f"{row['Symbol']:>10} | Score: {row['Composite_Score']:>6.2f} | "
                  f"Rating: {row['Rating']:>15} | Confidence: {row['Confidence']:.0%}")

        print("\n" + "="*70)
        print(f"Results saved to: {args.output}")
        print("="*70 + "\n")

    else:
        print("\nNo results generated. Check logs for errors.\n")


def analyze_single(args):
    """
    Analyze single announcement

    Parameters
    ----------
    args : argparse.Namespace
        Command line arguments
    """
    print("\n" + "="*70)
    print(f"PEAD TOOL - Analyzing {args.symbol}")
    print("="*70 + "\n")

    # Parse date
    announcement_date = datetime.strptime(args.date, '%Y-%m-%d')

    analyzer = PEADAnalyzer(use_cache=not args.no_cache)

    result = analyzer.analyze_announcement(
        symbol=args.symbol,
        announcement_date=announcement_date,
        visualize=args.visualize,
        output_dir=args.output
    )

    if result['success']:
        print("\n" + "="*70)
        print("ANALYSIS RESULTS")
        print("="*70 + "\n")

        composite = result['composite_score']

        # Print detailed report
        from src.scoring.composite_score import CompositeScorer
        scorer = CompositeScorer()
        report = scorer.get_detailed_report(composite)
        print(report)

        # Print CAR summary
        from src.models.car import CumulativeAbnormalReturns
        car_obj = CumulativeAbnormalReturns()
        car_obj.cars = result['car_data']
        print(car_obj.get_summary())

        print("\n" + "="*70)
        print(f"Results saved to: {args.output}")
        print("="*70 + "\n")

    else:
        print(f"\nAnalysis failed: {result.get('error', 'Unknown error')}\n")


def analyze_batch(args):
    """
    Analyze batch of stocks from CSV file

    Parameters
    ----------
    args : argparse.Namespace
        Command line arguments
    """
    import pandas as pd

    print("\n" + "="*70)
    print(f"PEAD TOOL - Batch Analysis from {args.file}")
    print("="*70 + "\n")

    # Read CSV file
    try:
        stocks_df = pd.read_csv(args.file)
        required_cols = ['symbol', 'announcement_date']

        if not all(col in stocks_df.columns for col in required_cols):
            print(f"Error: CSV must have columns: {required_cols}")
            return

        print(f"Loaded {len(stocks_df)} stocks from {args.file}\n")

    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Analyze each stock
    analyzer = PEADAnalyzer(use_cache=not args.no_cache)
    results = []

    for idx, row in stocks_df.iterrows():
        symbol = row['symbol']
        date_str = row['announcement_date']

        try:
            announcement_date = pd.to_datetime(date_str)

            print(f"\n{idx+1}/{len(stocks_df)}: Analyzing {symbol} on {announcement_date.date()}")

            result = analyzer.analyze_announcement(
                symbol=symbol,
                announcement_date=announcement_date,
                visualize=args.visualize,
                output_dir=args.output
            )

            if result['success']:
                composite = result['composite_score']
                car_data = result.get('car_data', {})
                market_model = result.get('market_model', {})

                # Extract component scores
                components = composite.get('components', {})

                # Extract CARs
                car_1d = car_data.get(1, {}).get('car_pct', 0)
                car_10d = car_data.get(10, {}).get('car_pct', 0)
                car_30d = car_data.get(30, {}).get('car_pct', 0)
                car_60d = car_data.get(60, {}).get('car_pct', 0)
                car_90d = car_data.get(90, {}).get('car_pct', 0)

                # Check for significance
                car_30d_sig = car_data.get(30, {}).get('significant', False)
                car_60d_sig = car_data.get(60, {}).get('significant', False)
                car_90d_sig = car_data.get(90, {}).get('significant', False)

                results.append({
                    'Symbol': symbol,
                    'Announcement_Date': announcement_date,
                    'Composite_Score': composite['composite_score'],
                    'Rating': composite['rating'],
                    'Confidence': composite['confidence'],
                    'Recommendation': composite.get('recommendation', 'N/A'),

                    # Component scores
                    'Earnings_Surprise': components.get('earnings_surprise', 0),
                    'Price_Reaction': components.get('price_reaction', 0),
                    'Drift_Confirmation': components.get('drift_confirmation', 0),
                    'Earnings_Quality': components.get('earnings_quality', 0),
                    'Contextual': components.get('contextual', 0),

                    # CAR values
                    'CAR_1d': car_1d,
                    'CAR_10d': car_10d,
                    'CAR_30d': car_30d,
                    'CAR_60d': car_60d,
                    'CAR_90d': car_90d,

                    # Significance flags
                    'CAR_30d_Significant': car_30d_sig,
                    'CAR_60d_Significant': car_60d_sig,
                    'CAR_90d_Significant': car_90d_sig,

                    # Market model
                    'Alpha': market_model.get('alpha', 0),
                    'Beta': market_model.get('beta', 0),
                    'R_Squared': market_model.get('r_squared', 0)
                })
            else:
                print(f"   Failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"   Error: {e}")
            continue

    # Print summary
    if results:
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('Composite_Score', ascending=False)

        # Save comprehensive CSV
        output_path = Path(args.output) / 'batch_analysis_summary.csv'
        results_df.to_csv(output_path, index=False)

        print("\n" + "="*100)
        print("BATCH ANALYSIS SUMMARY - DETAILED REPORT")
        print("="*100 + "\n")

        # Print each stock with detailed breakdown
        for idx, row in results_df.iterrows():
            print(f"\n{'='*100}")
            print(f"#{idx+1}. {row['Symbol']} | Announcement: {row['Announcement_Date'].date()}")
            print(f"{'='*100}")

            print(f"\n  COMPOSITE SCORE: {row['Composite_Score']:.2f}/100")
            print(f"  Rating:          {row['Rating']}")
            print(f"  Confidence:      {row['Confidence']:.0%}")
            print(f"  Recommendation:  {row['Recommendation']}")

            print(f"\n  COMPONENT BREAKDOWN:")
            print(f"    • Earnings Surprise:    {row['Earnings_Surprise']:>6.2f} pts")
            print(f"    • Price Reaction:       {row['Price_Reaction']:>6.2f} pts")
            print(f"    • Drift Confirmation:   {row['Drift_Confirmation']:>6.2f} pts")
            print(f"    • Earnings Quality:     {row['Earnings_Quality']:>6.2f} pts")
            print(f"    • Contextual Factors:   {row['Contextual']:>6.2f} pts")

            print(f"\n  CUMULATIVE ABNORMAL RETURNS (CAR):")
            print(f"    • 1-day  CAR:  {row['CAR_1d']:>7.2%}")
            print(f"    • 10-day CAR:  {row['CAR_10d']:>7.2%}")
            print(f"    • 30-day CAR:  {row['CAR_30d']:>7.2%} {'✓ Significant' if row['CAR_30d_Significant'] else ''}")
            print(f"    • 60-day CAR:  {row['CAR_60d']:>7.2%} {'✓ Significant' if row['CAR_60d_Significant'] else ''}")
            print(f"    • 90-day CAR:  {row['CAR_90d']:>7.2%} {'✓ Significant' if row['CAR_90d_Significant'] else ''}")

            print(f"\n  MARKET MODEL:")
            print(f"    • Alpha (α):   {row['Alpha']:>7.4f}")
            print(f"    • Beta (β):    {row['Beta']:>7.4f}")
            print(f"    • R-squared:   {row['R_Squared']:>7.4f}")

            # Interpretation
            print(f"\n  KEY INSIGHTS:")

            # Drift direction
            if row['CAR_90d'] > 0.05:
                drift_msg = f"    ✓ Strong positive drift detected (+{row['CAR_90d']:.2%} over 90 days)"
            elif row['CAR_90d'] > 0.02:
                drift_msg = f"    • Moderate positive drift (+{row['CAR_90d']:.2%} over 90 days)"
            elif row['CAR_90d'] < -0.05:
                drift_msg = f"    ✗ Strong negative drift detected ({row['CAR_90d']:.2%} over 90 days)"
            elif row['CAR_90d'] < -0.02:
                drift_msg = f"    • Moderate negative drift ({row['CAR_90d']:.2%} over 90 days)"
            else:
                drift_msg = f"    • Minimal drift ({row['CAR_90d']:.2%} over 90 days)"
            print(drift_msg)

            # Beta interpretation
            if row['Beta'] > 1.2:
                beta_msg = "    • High beta (>1.2): Stock more volatile than market"
            elif row['Beta'] > 0.8:
                beta_msg = "    • Moderate beta (0.8-1.2): Stock moves with market"
            else:
                beta_msg = "    • Low beta (<0.8): Stock less volatile than market"
            print(beta_msg)

            # Model fit
            if row['R_Squared'] > 0.5:
                fit_msg = f"    • Strong market model fit (R²={row['R_Squared']:.2%})"
            elif row['R_Squared'] > 0.3:
                fit_msg = f"    • Moderate market model fit (R²={row['R_Squared']:.2%})"
            else:
                fit_msg = f"    • Weak market model fit (R²={row['R_Squared']:.2%}) - idiosyncratic factors dominate"
            print(fit_msg)

            # Score interpretation
            if row['Composite_Score'] >= 60:
                score_msg = "    ✓ Strong PEAD opportunity - high confidence for trading"
            elif row['Composite_Score'] >= 40:
                score_msg = "    • Moderate PEAD signal - consider with other factors"
            elif row['Composite_Score'] >= 20:
                score_msg = "    • Weak PEAD signal - limited actionable opportunity"
            else:
                score_msg = "    ✗ Negative or no PEAD signal - avoid position"
            print(score_msg)

        print(f"\n{'='*100}")
        print(f"RANKING SUMMARY")
        print(f"{'='*100}\n")

        # Quick summary table
        summary_cols = ['Symbol', 'Composite_Score', 'Rating', 'CAR_90d', 'Beta', 'R_Squared']
        print(results_df[summary_cols].to_string(index=False))

        print(f"\n{'='*100}")
        print(f"Detailed report saved to: {output_path}")
        print(f"Individual stock visualizations in: {args.output}/[SYMBOL]/")
        print(f"{'='*100}\n")
    else:
        print("\nNo successful analyses.\n")


def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(
        description='PEAD Tool - Post-Earnings Announcement Drift Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze top 10 recent announcements
  python main.py --mode recent --top 10

  # Analyze specific stock announcement
  python main.py --mode single --symbol RELIANCE --date 2024-01-15

  # Analyze stocks from CSV file (stocks.csv)
  python main.py --mode batch --file stocks.csv

  # Run without cache
  python main.py --mode recent --top 5 --no-cache

  # Disable visualizations
  python main.py --mode recent --top 10 --no-visualize
        """
    )

    parser.add_argument(
        '--mode',
        choices=['recent', 'single', 'batch'],
        required=True,
        help='Analysis mode: recent announcements, single stock, or batch from CSV'
    )

    parser.add_argument(
        '--top',
        type=int,
        default=10,
        help='Number of recent announcements to analyze (for recent mode)'
    )

    parser.add_argument(
        '--symbol',
        type=str,
        help='Stock symbol (for single mode)'
    )

    parser.add_argument(
        '--date',
        type=str,
        help='Announcement date in YYYY-MM-DD format (for single mode)'
    )

    parser.add_argument(
        '--file',
        type=str,
        default='stocks.csv',
        help='CSV file with stocks to analyze (for batch mode)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='./output',
        help='Output directory for results'
    )

    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable data caching'
    )

    parser.add_argument(
        '--no-visualize',
        dest='visualize',
        action='store_false',
        help='Disable visualizations'
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Validate arguments
    if args.mode == 'single':
        if not args.symbol or not args.date:
            parser.error("--symbol and --date are required for single mode")
    elif args.mode == 'batch':
        if not Path(args.file).exists():
            parser.error(f"File not found: {args.file}")

    # Create output directory
    Path(args.output).mkdir(parents=True, exist_ok=True)

    # Run analysis
    try:
        if args.mode == 'recent':
            analyze_recent(args)
        elif args.mode == 'single':
            analyze_single(args)
        elif args.mode == 'batch':
            analyze_batch(args)

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.\n")
        sys.exit(1)

    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n\nFatal error: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
