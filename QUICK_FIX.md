# ⚡ QUICK FIX - Import Errors

## Problem
Getting "No module named 'src.data'" or "No module named 'pandas'" errors.

## Solution

**Sab imports sahi hain! Bas dependencies install karne hain.**

### On macOS (Your System):

```bash
# 1. Go to project directory
cd /Users/yashbhanushali/Desktop/code/pead-tool

# 2. Pull latest code
git pull origin claude/quant-code-structure-01RznrcoXoytchaEwLtteW4M

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install ALL dependencies (this will take 2-3 minutes)
pip install -r requirements.txt

# 5. Verify everything works
python3 verify_setup.py

# 6. Run the tool!
python main.py --mode recent --top 5
```

### If pip install is slow or failing:

Install core packages first:

```bash
# Minimal install (fastest)
pip install numpy pandas scipy matplotlib yfinance nse

# Then test
python3 verify_setup.py
```

### If you see specific errors:

**Error: "No space left on device"**
```bash
pip install --no-cache-dir -r requirements.txt
```

**Error: "Permission denied"**
```bash
pip install --user -r requirements.txt
```

**Error: "Could not build wheels"**
```bash
# Install build tools first
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## Why This Happens

The code imports pandas/numpy/etc. If these aren't installed, Python can't load the modules, even though the import structure is correct.

Think of it like:
- ✅ Imports are correct (file paths are right)
- ❌ Dependencies missing (pandas, numpy not installed)

## Verify It's Fixed

After installing dependencies, this should work:

```bash
python3 -c "from src.analysis.pead_analyzer import PEADAnalyzer; print('✅ All working!')"
```

## Still Having Issues?

Run this and send me the output:

```bash
python3 verify_setup.py
```

This will show exactly what's missing.

---

**Bottom line:** Run `pip install -r requirements.txt` in your venv, phir sab kaam karega! 🚀
