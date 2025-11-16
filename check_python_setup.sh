#!/bin/bash
# Check Python setup on macOS with Homebrew

echo "🔍 Checking Python Setup on macOS..."
echo "=========================================="

# Check which Python is being used
echo -e "\n📍 Python Location:"
which python3
python3 --version

# Check if it's Homebrew Python
echo -e "\n🍺 Homebrew Python Check:"
if which python3 | grep -q "brew"; then
    echo "✓ Using Homebrew Python"
else
    echo "⚠ Not using Homebrew Python (might be system Python)"
fi

# Check pip
echo -e "\n📦 Pip Location:"
which pip3
pip3 --version

# Check virtual environment
echo -e "\n🌐 Virtual Environment:"
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✓ Virtual environment active: $VIRTUAL_ENV"
    echo "Python: $(which python)"
    echo "Pip: $(which pip)"
else
    echo "⚠ No virtual environment active"
    echo "Run: source venv/bin/activate"
fi

# Check Python path
echo -e "\n🛤️  Python Path:"
python3 -c "import sys; print('\n'.join(sys.path[:5]))"

# Check if pandas can be imported (after venv activation)
echo -e "\n📚 Test pandas import:"
python3 -c "import pandas; print('✓ pandas installed:', pandas.__version__)" 2>/dev/null || echo "✗ pandas NOT installed - run: pip install pandas"

echo -e "\n=========================================="
echo "💡 Next Steps:"
echo "1. Make sure virtual env is active: source venv/bin/activate"
echo "2. Install dependencies: pip install -r requirements.txt"
echo "3. Run: python main.py --help"
