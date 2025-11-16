#!/usr/bin/env python3
"""
Test imports step by step to find exact problem
"""
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 Testing imports step by step...")
print("=" * 60)

# Step 1: Check pandas
print("\n1️⃣ Testing pandas import...")
try:
    import pandas as pd
    print(f"   ✅ pandas {pd.__version__} imported successfully")
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    sys.exit(1)

# Step 2: Check numpy
print("\n2️⃣ Testing numpy import...")
try:
    import numpy as np
    print(f"   ✅ numpy {np.__version__} imported successfully")
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    sys.exit(1)

# Step 3: Test basic src imports
print("\n3️⃣ Testing src.config...")
try:
    from src.config.settings import config
    print(f"   ✅ src.config.settings works")
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Test data module
print("\n4️⃣ Testing src.data.nse_fetcher...")
try:
    from src.data.nse_fetcher import NSEDataFetcher
    print(f"   ✅ NSEDataFetcher imported")
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: Test models
print("\n5️⃣ Testing src.models.market_model...")
try:
    from src.models.market_model import MarketModel
    print(f"   ✅ MarketModel imported")
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 6: Test main analyzer
print("\n6️⃣ Testing src.analysis.pead_analyzer...")
try:
    from src.analysis.pead_analyzer import PEADAnalyzer
    print(f"   ✅ PEADAnalyzer imported")

    # Try to instantiate
    analyzer = PEADAnalyzer()
    print(f"   ✅ PEADAnalyzer instantiated successfully")
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("🎉 ALL IMPORTS WORKING!")
print("\n✅ You're ready to run:")
print("   python main.py --mode recent --top 5")
print("=" * 60)
