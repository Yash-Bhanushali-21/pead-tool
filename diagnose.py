#!/usr/bin/env python3
"""
Complete diagnostic - run this on your Mac to find the exact issue
"""
import sys
import os
from pathlib import Path

print("🩺 PEAD Tool Diagnostics")
print("=" * 70)

# 1. Python info
print("\n📍 Python Information:")
print(f"   Python: {sys.executable}")
print(f"   Version: {sys.version.split()[0]}")
print(f"   Platform: {sys.platform}")

# 2. Virtual environment check
print("\n🌐 Virtual Environment:")
in_venv = hasattr(sys, 'real_prefix') or (
    hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
)
if in_venv:
    print(f"   ✅ In virtual environment")
    print(f"   Location: {sys.prefix}")
else:
    print(f"   ⚠️  NOT in virtual environment!")
    print(f"   💡 Run: source venv/bin/activate")

# 3. Project root check
print("\n📁 Project Setup:")
project_root = Path(__file__).parent
print(f"   Root: {project_root}")
print(f"   Exists: {project_root.exists()}")

src_dir = project_root / "src"
print(f"   src/ exists: {src_dir.exists()}")

# Add to path
sys.path.insert(0, str(project_root))
print(f"   Added to sys.path: ✓")

# 4. Test pandas
print("\n📦 Testing pandas:")
try:
    import pandas as pd
    print(f"   ✅ pandas {pd.__version__}")
    pandas_ok = True
except ImportError as e:
    print(f"   ❌ pandas NOT found")
    print(f"   Error: {e}")
    print(f"   💡 Run: pip install pandas")
    pandas_ok = False

# 5. Test numpy
print("\n📦 Testing numpy:")
try:
    import numpy as np
    print(f"   ✅ numpy {np.__version__}")
except ImportError:
    print(f"   ❌ numpy NOT found")
    print(f"   💡 Run: pip install numpy")

# 6. Test project imports (only if pandas OK)
if pandas_ok:
    print("\n🔧 Testing Project Imports:")

    # Config
    try:
        from src.config.settings import config
        print(f"   ✅ src.config.settings")
    except Exception as e:
        print(f"   ❌ src.config.settings: {e}")

    # Data
    try:
        from src.data.nse_fetcher import NSEDataFetcher
        print(f"   ✅ src.data.nse_fetcher")
    except Exception as e:
        print(f"   ❌ src.data.nse_fetcher: {e}")

    # Models
    try:
        from src.models.market_model import MarketModel
        print(f"   ✅ src.models.market_model")
    except Exception as e:
        print(f"   ❌ src.models.market_model: {e}")

    # Analyzer
    try:
        from src.analysis.pead_analyzer import PEADAnalyzer
        print(f"   ✅ src.analysis.pead_analyzer")

        # Try to create instance
        analyzer = PEADAnalyzer()
        print(f"   ✅ PEADAnalyzer() instantiated!")

    except Exception as e:
        print(f"   ❌ src.analysis.pead_analyzer: {e}")
        import traceback
        traceback.print_exc()

# 7. Summary
print("\n" + "=" * 70)
print("📊 Summary:")

if not in_venv:
    print("\n❌ PROBLEM FOUND: Not in virtual environment")
    print("\n🔧 FIX:")
    print("   cd /Users/yashbhanushali/Desktop/code/pead-tool")
    print("   source venv/bin/activate")
    print("   python diagnose.py")

elif not pandas_ok:
    print("\n❌ PROBLEM FOUND: pandas not installed in this environment")
    print("\n🔧 FIX:")
    print("   Make sure venv is active (see prompt for (venv))")
    print("   pip install pandas numpy scipy yfinance matplotlib")
    print("   python diagnose.py")

else:
    print("\n✅ Everything looks good!")
    print("\n🚀 You can now run:")
    print("   python main.py --mode recent --top 5")

print("=" * 70)
