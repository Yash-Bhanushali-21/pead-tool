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
                results.append({
                    'Symbol': symbol,
                    'Announcement_Date': announcement_date,
                    'Composite_Score': result['composite_score']['score'],
                    'Rating': result['composite_score']['rating'],
                    'Confidence': result['composite_score']['confidence']
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

        print("\n" + "="*70)
        print("BATCH ANALYSIS SUMMARY")
        print("="*70 + "\n")
        print(results_df.to_string(index=False))

        # Save to CSV
        output_path = Path(args.output) / 'batch_analysis_summary.csv'
        results_df.to_csv(output_path, index=False)

        print("\n" + "="*70)
        print(f"Results saved to: {output_path}")
        print("="*70 + "\n")
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
