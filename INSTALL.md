# Installation Guide

## Quick Install (Recommended)

### Option 1: Development Install (Recommended)

This installs the package in editable mode so you can modify the code:

```bash
# 1. Clone the repository
git clone <repository-url>
cd pead-tool

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install in development mode
pip install -e .

# 4. Verify installation
python -c "from src.analysis.pead_analyzer import PEADAnalyzer; print('✅ Installation successful!')"
```

### Option 2: Direct Install (No Setup.py)

If you don't want to install as a package:

```bash
# 1. Clone and setup virtual environment (same as above)
git clone <repository-url>
cd pead-tool
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies only
pip install -r requirements.txt

# 3. Run directly (the scripts handle Python path)
python main.py --mode recent --top 5
```

## System Requirements

- **Python**: 3.8 or higher
- **OS**: macOS, Linux, or Windows
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 500MB for dependencies + data cache

## Dependency Installation

### Core Dependencies

```bash
pip install numpy pandas scipy statsmodels
```

### Data Sources

```bash
pip install yfinance nse requests beautifulsoup4
```

### Document Processing

```bash
pip install PyPDF2 pdfplumber textblob
```

### Visualization

```bash
pip install matplotlib seaborn
```

### All at once

```bash
pip install -r requirements.txt
```

## Common Installation Issues

### Issue 1: "No module named 'src'"

**Solution**: The scripts now handle this automatically by adding the project root to Python path.

If you still see this error, use development install:
```bash
pip install -e .
```

### Issue 2: "ImportError: No module named 'nse'"

**Solution**: The `nse` package might have installation issues.

```bash
# Try installing directly from PyPI
pip install nse --upgrade

# If that fails, try:
pip install git+https://github.com/vsjha18/nse_pricevolume.git
```

### Issue 3: PDF parsing errors

**Solution**: Install additional dependencies:

```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils

# Then reinstall pdfplumber
pip install --upgrade pdfplumber
```

### Issue 4: "No module named 'tkinter'" (for matplotlib)

**Solution**: Install tkinter for your system:

```bash
# macOS
brew install python-tk

# Ubuntu/Debian
sudo apt-get install python3-tk

# Or use a different matplotlib backend
export MPLBACKEND=Agg
```

### Issue 5: Slow installation

**Solution**: Use pip cache and parallel downloads:

```bash
pip install --cache-dir ~/.cache/pip --use-pep517 -r requirements.txt
```

## Verification

After installation, verify everything works:

```bash
# Test imports
python -c "
from src.data.data_manager import DataManager
from src.models.market_model import MarketModel
from src.scoring.composite_score import CompositeScorer
from src.analysis.pead_analyzer import PEADAnalyzer
print('✅ All imports successful!')
"

# Test basic functionality
python main.py --help
```

## Optional: Jupyter Notebook Support

If you want to use PEAD tool in Jupyter notebooks:

```bash
pip install jupyter ipykernel
python -m ipykernel install --user --name=pead-tool

# Launch Jupyter
jupyter notebook
```

Then in a notebook:
```python
import sys
sys.path.insert(0, '/path/to/pead-tool')

from src.analysis.pead_analyzer import PEADAnalyzer
analyzer = PEADAnalyzer()
```

## Docker Installation (Advanced)

If you want to run in Docker:

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install -e .

CMD ["python", "main.py", "--mode", "recent", "--top", "10"]
```

Build and run:
```bash
docker build -t pead-tool .
docker run -v $(pwd)/output:/app/output pead-tool
```

## Updating

To update to the latest version:

```bash
cd pead-tool
git pull origin main

# If using development install
pip install -e . --upgrade

# If using direct install
pip install -r requirements.txt --upgrade
```

## Uninstallation

```bash
# If installed with setup.py
pip uninstall pead-tool

# Remove virtual environment
deactivate
rm -rf venv

# Remove data cache
rm -rf data/
```

## Getting Help

If you still have installation issues:

1. Check Python version: `python --version` (must be 3.8+)
2. Check pip version: `pip --version`
3. Try creating a fresh virtual environment
4. Check the logs in the terminal
5. Open an issue on GitHub with:
   - Your OS and Python version
   - Complete error message
   - Output of `pip list`

---

**Ready to analyze? Go to [QUICKSTART.md](QUICKSTART.md)**
