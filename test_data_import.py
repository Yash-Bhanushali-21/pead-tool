#!/usr/bin/env python3
"""
Specific test for src.data import issue
"""
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 Debugging src.data import issue")
print("=" * 60)

# Show Python path
print("\n1️⃣ Python sys.path:")
for i, p in enumerate(sys.path[:5]):
    print(f"   [{i}] {p}")

# Check if src exists
print("\n2️⃣ Checking src/ directory:")
src_path = Path(__file__).parent / "src"
print(f"   Path: {src_path}")
print(f"   Exists: {src_path.exists()}")
print(f"   Is dir: {src_path.is_dir()}")

# Check src/data exists
print("\n3️⃣ Checking src/data/ directory:")
data_path = src_path / "data"
print(f"   Path: {data_path}")
print(f"   Exists: {data_path.exists()}")
print(f"   Is dir: {data_path.is_dir()}")

# List files in src/data
if data_path.exists():
    print(f"\n   Files in src/data/:")
    for f in data_path.iterdir():
        print(f"      - {f.name}")

# Check __init__.py
init_file = data_path / "__init__.py"
print(f"\n4️⃣ Checking __init__.py:")
print(f"   Path: {init_file}")
print(f"   Exists: {init_file.exists()}")
if init_file.exists():
    print(f"   Size: {init_file.stat().st_size} bytes")
    print(f"   Content:")
    with open(init_file) as f:
        for i, line in enumerate(f, 1):
            print(f"      {i}: {line.rstrip()}")

# Try importing src
print("\n5️⃣ Importing src:")
try:
    import src
    print(f"   ✅ src imported")
    print(f"   src.__file__: {src.__file__}")
    print(f"   src.__path__: {src.__path__}")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()

# Try importing src.data
print("\n6️⃣ Importing src.data:")
try:
    import src.data
    print(f"   ✅ src.data imported")
    print(f"   src.data.__file__: {src.data.__file__}")
    if hasattr(src.data, '__path__'):
        print(f"   src.data.__path__: {src.data.__path__}")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()

# Try importing nse_fetcher module
print("\n7️⃣ Importing src.data.nse_fetcher:")
try:
    from src.data import nse_fetcher
    print(f"   ✅ nse_fetcher module imported")
    print(f"   Module file: {nse_fetcher.__file__}")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()

# Try importing NSEDataFetcher class
print("\n8️⃣ Importing NSEDataFetcher class:")
try:
    from src.data.nse_fetcher import NSEDataFetcher
    print(f"   ✅ NSEDataFetcher imported")
    print(f"   Class: {NSEDataFetcher}")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
