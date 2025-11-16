#!/usr/bin/env python3
"""
Verify PEAD Tool Setup
Run this to check what's missing
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 Verifying PEAD Tool Setup...")
print("=" * 60)

# Check Python version
print(f"\n✓ Python version: {sys.version.split()[0]}")

# Check if dependencies are installed
print("\n📦 Checking dependencies:")

dependencies = [
    'numpy',
    'pandas',
    'scipy',
    'statsmodels',
    'yfinance',
    'matplotlib',
    'seaborn',
    'requests',
    'beautifulsoup4',
    'textblob',
]

missing = []
for dep in dependencies:
    try:
        __import__(dep)
        print(f"  ✓ {dep}")
    except ImportError:
        print(f"  ✗ {dep} - NOT INSTALLED")
        missing.append(dep)

# Check project imports
print("\n🔧 Checking project imports:")

try:
    from src.config.settings import config
    print("  ✓ src.config.settings")
except Exception as e:
    print(f"  ✗ src.config.settings - {e}")

try:
    from src.data.data_manager import DataManager
    print("  ✓ src.data.data_manager")
except Exception as e:
    print(f"  ✗ src.data.data_manager - {e}")

try:
    from src.models.market_model import MarketModel
    print("  ✓ src.models.market_model")
except Exception as e:
    print(f"  ✗ src.models.market_model - {e}")

try:
    from src.analysis.pead_analyzer import PEADAnalyzer
    print("  ✓ src.analysis.pead_analyzer")
    print("\n🎉 All project imports working!")
except Exception as e:
    print(f"  ✗ src.analysis.pead_analyzer - {e}")

# Summary
print("\n" + "=" * 60)
if missing:
    print(f"\n❌ Missing {len(missing)} dependencies!")
    print("\n🔧 To fix, run:")
    print(f"   pip install {' '.join(missing)}")
    print("\n   OR install all at once:")
    print("   pip install -r requirements.txt")
else:
    print("\n✅ All dependencies installed!")
    print("\n🚀 Ready to run:")
    print("   python main.py --mode recent --top 5")

print("\n" + "=" * 60)
