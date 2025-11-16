# PEAD Tool - Quick Start Guide

## Installation (5 minutes)

### Recommended: Development Install

```bash
# 1. Clone repository
git clone <repository-url>
cd pead-tool

# 2. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install in development mode
pip install -e .

# 4. Verify installation
python -c "from src.analysis.pead_analyzer import PEADAnalyzer; print('✅ Installation successful!')"
```

### Alternative: Direct Install

```bash
# Steps 1-2 same as above

# 3. Install dependencies only
pip install -r requirements.txt

# 4. Run directly (scripts handle Python path automatically)
python main.py --help
```

**Having issues?** See [INSTALL.md](INSTALL.md) for troubleshooting.

## First Analysis (2 minutes)

### Option 1: Analyze Recent Announcements (Recommended)

```bash
python main.py --mode recent --top 10
```

This will:
- Fetch 10 most recent earnings announcements from NSE
- Analyze each using the comprehensive PEAD scoring system
- Generate visualizations and save to `./output/`
- Create a summary CSV with all results

### Option 2: Analyze Specific Stock

```bash
python main.py --mode single --symbol RELIANCE --date 2024-01-15
```

Replace `RELIANCE` and `2024-01-15` with your target stock and announcement date.

## Understanding the Output

### Console Output

You'll see:
1. **Progress logs** for each analysis step
2. **Summary table** with scores for all stocks
3. **Top opportunities** ranked by composite score

### Files Generated

```
output/
├── pead_analysis_summary.csv      # Summary of all analyses
├── comparison_dashboard.png        # Visual comparison
└── RELIANCE/                       # Per-stock folders
    ├── RELIANCE_price.png          # Price chart
    ├── RELIANCE_scores.png         # Score breakdown
    ├── RELIANCE_ar.png             # Abnormal returns
    └── RELIANCE_car.png            # CAR evolution
```

### Interpreting Scores

| Score Range | Rating | Interpretation |
|------------|--------|----------------|
| 80-100 | STRONG BUY | Very high PEAD probability |
| 65-79 | BUY | High PEAD probability |
| 50-64 | MODERATE BUY | Moderate PEAD signal |
| 35-49 | HOLD | Mixed signals |
| 20-34 | MODERATE SELL | Weak/negative drift |
| 0-19 | SELL | Negative drift likely |
| <0 | STRONG SELL | Strong negative drift |

### Score Components

1. **Earnings Surprise (25%)**: How big was the earnings beat/miss?
2. **Price Reaction (20%)**: Did market under-react? (Best for PEAD)
3. **Drift Confirmation (25%)**: Is drift actually happening?
4. **Earnings Quality (15%)**: Are earnings high quality?
5. **Contextual (15%)**: Favorable market/sector conditions?

## Example Use Cases

### Find Best PEAD Opportunities This Week

```bash
# Analyze top 20 recent announcements
python main.py --mode recent --top 20

# Sort by score in the CSV
# Look for: High score + High confidence + Positive CAR(10d)
```

### Deep Dive on Specific Stock

```bash
# Analyze with visualizations
python main.py --mode single --symbol TCS --date 2024-01-10

# Check output/TCS/ folder for:
# - Price charts showing drift
# - CAR evolution (should be positive and significant)
# - Component scores (identify strengths/weaknesses)
```

### Weekly Monitoring Workflow

```bash
# Monday morning: Analyze last week's announcements
python main.py --mode recent --top 30 --output ./results/$(date +%Y%m%d)

# Review the summary CSV
# Filter for scores > 65 and confidence > 0.7

# Deep dive on top 3-5 opportunities
python main.py --mode single --symbol <TOP_PICK> --date <DATE>
```

## Common Options

```bash
# Disable caching (always fetch fresh data)
python main.py --mode recent --top 10 --no-cache

# Faster analysis (no visualizations)
python main.py --mode recent --top 20 --no-visualize

# Verbose logging (for debugging)
python main.py --mode recent --top 5 --verbose

# Custom output directory
python main.py --mode recent --top 10 --output ./my_results
```

## Tips for Better Results

### 1. Data Quality
- Run analyses a few days after announcement (allows drift to develop)
- Avoid analysis on announcement day (incomplete data)
- Use `--no-cache` if market data seems stale

### 2. Interpretation
- **High Score + High Confidence** = Strong signal
- **High Score + Low Confidence** = Data quality issues, be cautious
- Look at multiple CAR windows: Consistent positive = stronger signal
- Check component breakdown: Where is the signal coming from?

### 3. Risk Management
- PEAD is a statistical edge, not a guarantee
- Use position sizing and stop losses
- Consider holding period based on CAR windows (typically 10-60 days)
- Monitor for reversal signals

### 4. Best Practices
- Analyze multiple stocks for portfolio approach
- Combine with your fundamental analysis
- Track performance of tool's recommendations
- Adjust weights in config based on backtest results

## Troubleshooting

### "No announcements found"
- NSE data might be temporarily unavailable
- Try running with `--no-cache`
- Check internet connection

### "Insufficient data for analysis"
- Stock might be newly listed or illiquid
- Try a different date or stock
- Check if symbol is correct (use NSE format)

### Plots not generating
- Check matplotlib backend: `import matplotlib; print(matplotlib.get_backend())`
- Try running without `--no-visualize` flag
- Check write permissions in output directory

### Slow performance
- Use `--no-visualize` for faster runs
- Enable caching (don't use `--no-cache`)
- Reduce `--top` number for large batches

## Next Steps

1. **Read full README.md** for methodology details
2. **Run example_usage.py** for advanced usage patterns
3. **Customize src/config/settings.py** for your preferences
4. **Backtest** the tool's recommendations against historical data
5. **Integrate** with your trading workflow

## Getting Help

- Check logs in `pead_analysis.log`
- Review code documentation in source files
- Open issue on GitHub
- See README.md for academic references on PEAD

---

**Ready to find alpha in the Indian markets? Let's go! 🚀**

```bash
python main.py --mode recent --top 10
```
