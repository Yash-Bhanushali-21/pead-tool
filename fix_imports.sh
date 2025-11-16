#!/bin/bash
# Fix import issues by clearing cache and reinstalling

echo "🔧 Fixing import issues..."

# 1. Remove all Python cache
echo "1️⃣ Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
echo "   ✓ Cache cleared"

# 2. Remove .pyc files
echo "2️⃣ Removing compiled files..."
find . -name "*.pyc" -delete 2>/dev/null
echo "   ✓ Compiled files removed"

# 3. Verify directory structure
echo "3️⃣ Verifying src/ structure..."
ls -la src/
echo ""
ls -la src/data/

# 4. Test import
echo "4️⃣ Testing import..."
python3 << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

print("\nTesting src.data import:")
try:
    import src.data
    print("✅ src.data package imported")
except Exception as e:
    print(f"❌ Failed: {e}")

print("\nTesting direct file import:")
try:
    from src.data import nse_fetcher
    print("✅ src.data.nse_fetcher module imported")
except Exception as e:
    print(f"❌ Failed: {e}")

print("\nTesting class import:")
try:
    from src.data.nse_fetcher import NSEDataFetcher
    print("✅ NSEDataFetcher class imported")
except Exception as e:
    print(f"❌ Failed: {e}")
EOF

echo ""
echo "✅ Fix script completed!"
echo ""
echo "Now run: python diagnose.py"
