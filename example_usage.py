#!/usr/bin/env python3
"""
Example Usage of PEAD Tool

This script demonstrates various ways to use the PEAD analysis tool
"""

import sys
from pathlib import Path
from datetime import datetime
import logging

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.analysis.pead_analyzer import PEADAnalyzer
from src.config.settings import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)


def example_1_analyze_recent():
    """Example 1: Analyze recent announcements"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Analyzing Top 5 Recent Announcements")
    print("="*70 + "\n")

    analyzer = PEADAnalyzer(use_cache=True)

    results = analyzer.analyze_recent_announcements(
        n=5,
        visualize=True,
        output_dir="./output/example1"
    )

    if not results.empty:
        print("\nTop Opportunities:")
        print(results[['Symbol', 'Composite_Score', 'Rating', 'Confidence']].head(3))


def example_2_analyze_single():
    """Example 2: Analyze specific stock announcement"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Analyzing Single Stock")
    print("="*70 + "\n")

    analyzer = PEADAnalyzer(use_cache=True)

    # Example: TCS earnings (adjust date to recent announcement)
    result = analyzer.analyze_announcement(
        symbol='TCS',
        announcement_date=datetime(2024, 1, 10),
        visualize=True,
        output_dir="./output/example2"
    )

    if result['success']:
        composite = result['composite_score']
        print(f"\nSymbol: TCS")
        print(f"Score: {composite['composite_score']:.2f}/100")
        print(f"Rating: {composite['rating']}")
        print(f"Recommendation: {composite['recommendation']}")


def example_3_custom_configuration():
    """Example 3: Using custom configuration"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Custom Configuration")
    print("="*70 + "\n")

    # Modify configuration
    original_windows = config.CAR_WINDOWS.copy()
    config.CAR_WINDOWS = [1, 5, 10, 20, 30]  # Custom windows

    print(f"Using custom CAR windows: {config.CAR_WINDOWS}")

    analyzer = PEADAnalyzer(use_cache=True)

    # Run analysis with custom config
    results = analyzer.analyze_recent_announcements(
        n=3,
        visualize=False,
        output_dir="./output/example3"
    )

    # Restore original config
    config.CAR_WINDOWS = original_windows


def example_4_component_analysis():
    """Example 4: Detailed component analysis"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Detailed Component Analysis")
    print("="*70 + "\n")

    analyzer = PEADAnalyzer(use_cache=True)

    result = analyzer.analyze_announcement(
        symbol='RELIANCE',
        announcement_date=datetime(2024, 1, 15),
        visualize=True,
        output_dir="./output/example4"
    )

    if result['success']:
        scores = result['scores']

        print("\nComponent Breakdown:")
        print("-" * 50)
        print(f"Earnings Surprise:    {scores['earnings_surprise']['total']:>6.2f}")
        print(f"Price Reaction:       {scores['price_reaction']['total']:>6.2f}")
        print(f"Drift Confirmation:   {scores['drift_confirmation']['total']:>6.2f}")
        print(f"Earnings Quality:     {scores['earnings_quality']['total']:>6.2f}")
        print(f"Contextual:           {scores['contextual']['total']:>6.2f}")

        # CAR analysis
        print("\nCAR Analysis:")
        print("-" * 50)
        for window, data in result['car_data'].items():
            print(f"CAR({window:>2}d): {data['car_pct']:>7.2f}% "
                  f"(t={data['t_statistic']:>6.2f}, "
                  f"sig={'Yes' if data['significant'] else 'No'})")


def example_5_batch_symbols():
    """Example 5: Analyze specific list of symbols"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Batch Analysis of Specific Symbols")
    print("="*70 + "\n")

    symbols = ['TCS', 'INFY', 'WIPRO', 'HCLTECH']
    announcement_date = datetime(2024, 1, 10)  # Adjust to actual dates

    analyzer = PEADAnalyzer(use_cache=True)

    results = []
    for symbol in symbols:
        try:
            result = analyzer.analyze_announcement(
                symbol=symbol,
                announcement_date=announcement_date,
                visualize=False,
                output_dir=f"./output/example5/{symbol}"
            )

            if result['success']:
                composite = result['composite_score']
                results.append({
                    'Symbol': symbol,
                    'Score': composite['composite_score'],
                    'Rating': composite['rating']
                })
        except Exception as e:
            print(f"Failed to analyze {symbol}: {e}")

    if results:
        import pandas as pd
        df = pd.DataFrame(results)
        print("\nBatch Results:")
        print(df.to_string(index=False))


if __name__ == '__main__':
    import sys

    examples = {
        '1': example_1_analyze_recent,
        '2': example_2_analyze_single,
        '3': example_3_custom_configuration,
        '4': example_4_component_analysis,
        '5': example_5_batch_symbols,
    }

    if len(sys.argv) > 1 and sys.argv[1] in examples:
        # Run specific example
        examples[sys.argv[1]]()
    else:
        # Run all examples
        print("\n" + "="*70)
        print("RUNNING ALL EXAMPLES")
        print("="*70)

        for name, func in examples.items():
            try:
                func()
            except Exception as e:
                print(f"\nExample {name} failed: {e}\n")

    print("\n" + "="*70)
    print("EXAMPLES COMPLETE")
    print("="*70 + "\n")
