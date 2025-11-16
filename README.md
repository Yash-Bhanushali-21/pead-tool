# PEAD Tool - Post-Earnings Announcement Drift Analysis

A comprehensive quantitative analysis tool for identifying and scoring Post-Earnings Announcement Drift (PEAD) opportunities in Indian equity markets.

## Overview

PEAD (Post-Earnings Announcement Drift) is a well-documented market anomaly where stock prices continue to drift in the direction of an earnings surprise for weeks or months after the announcement. This tool provides rigorous quantitative analysis to identify and score PEAD opportunities.

## Features

### Core Analysis
- **Market Model Estimation**: Estimates α and β parameters using OLS regression on 120-day pre-announcement window
- **Abnormal Returns (AR)**: Calculates daily abnormal returns: AR = R_stock - (α + β * R_market)
- **Cumulative Abnormal Returns (CAR)**: Computes CAR for multiple windows (1, 10, 30, 60, 90 days)
- **Statistical Significance Testing**: T-tests, sign tests, and Wilcoxon tests for AR/CAR significance

### Comprehensive Scoring System (5 Components)

#### 1. Earnings Surprise (25% weight, max 70 points)
- **EPS Surprise**: YoY/QoQ EPS growth analysis
- **Revenue Surprise**: Revenue growth vs expectations
- **Margin Expansion**: Operating leverage and margin improvement
- **Guidance**: Forward guidance sentiment from announcement documents

#### 2. Price Reaction (20% weight, max 20 points)
- **Day 0 Return**: Under-reaction scoring (small move + big surprise = high PEAD potential)
- **Volume Spike**: Confirmation through trading volume analysis
- **Gap Analysis**: Gap open and continuation patterns

#### 3. Drift Confirmation (25% weight, max 25 points)
- **CAR Magnitude**: Weighted across short to medium windows
- **Statistical Significance**: P-value analysis across multiple windows
- **Relative Strength**: Outperformance vs NIFTY 50
- **Trend Continuity**: Technical indicators (MA, higher highs/lows, ROC)

#### 4. Earnings Quality (15% weight, max 15 points)
- **Source of Earnings**: Revenue-driven vs cost-cutting
- **Cash Flow Quality**: CFO/Net Income ratio
- **Balance Sheet Quality**: Working capital and liquidity trends

#### 5. Contextual Factors (15% weight, max 15 points)
- **Market Cap Category**: Mid-caps score highest (strongest PEAD)
- **Sector Tailwinds**: Industry-specific scoring
- **Track Record**: Historical earnings beat consistency
- **Macro Environment**: Market volatility regime analysis

### Data Sources
- **Primary**: NSE India (via `nse` package)
- **Fallback**: Yahoo Finance (for missing data)
- **Documents**: PDF download and parsing for sentiment analysis

### Output
- **Composite Score**: 0-100 score with rating (STRONG BUY to STRONG SELL)
- **Confidence Level**: Data quality and signal strength assessment
- **Visualizations**:
  - Price charts with announcement markers
  - CAR evolution plots
  - Component score breakdown
  - Comparison dashboards for multiple stocks
- **CSV Reports**: Detailed analysis summary for all stocks

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd pead-tool

# Install dependencies
pip install -r requirements.txt
```

## Dependencies

- numpy >= 1.24.0
- pandas >= 2.0.0
- scipy >= 1.10.0
- statsmodels >= 0.14.0
- yfinance >= 0.2.28
- nse >= 0.1.0
- PyPDF2 >= 3.0.0
- pdfplumber >= 0.10.0
- matplotlib >= 3.7.0
- seaborn >= 0.12.0
- textblob >= 0.17.1

## Usage

### Analyze Recent Announcements

```bash
# Analyze top 10 recent earnings announcements
python main.py --mode recent --top 10

# With custom output directory
python main.py --mode recent --top 10 --output ./results

# Without caching (fresh data fetch)
python main.py --mode recent --top 5 --no-cache
```

### Analyze Specific Stock

```bash
# Analyze specific announcement
python main.py --mode single --symbol RELIANCE --date 2024-01-15

# Multiple examples
python main.py --mode single --symbol TCS --date 2024-01-10
python main.py --mode single --symbol INFY --date 2024-01-12
```

### Advanced Options

```bash
# Verbose logging
python main.py --mode recent --top 10 --verbose

# Disable visualizations (faster)
python main.py --mode recent --top 10 --no-visualize

# Help
python main.py --help
```

## Architecture

```
pead-tool/
├── src/
│   ├── config/
│   │   └── settings.py          # Configuration parameters
│   ├── data/
│   │   ├── nse_fetcher.py       # NSE data fetching
│   │   ├── yahoo_fetcher.py     # Yahoo Finance fallback
│   │   └── data_manager.py      # Unified data interface with caching
│   ├── documents/
│   │   ├── pdf_downloader.py    # Download announcements
│   │   └── pdf_parser.py        # PDF parsing and sentiment
│   ├── models/
│   │   ├── market_model.py      # α, β estimation (OLS)
│   │   ├── abnormal_returns.py  # AR calculation
│   │   └── car.py               # CAR computation
│   ├── scoring/
│   │   ├── earnings_surprise.py # Component 1 scorer
│   │   ├── price_reaction.py    # Component 2 scorer
│   │   ├── drift_confirmation.py# Component 3 scorer
│   │   ├── earnings_quality.py  # Component 4 scorer
│   │   ├── contextual.py        # Component 5 scorer
│   │   └── composite_score.py   # Final composite scoring
│   ├── analysis/
│   │   └── pead_analyzer.py     # Main orchestrator
│   └── utils/
│       ├── statistical.py       # Statistical utilities
│       └── visualization.py     # Plotting utilities
├── main.py                       # Entry point
├── requirements.txt
└── README.md
```

## Configuration

Edit `src/config/settings.py` to customize:

- **Market Model**: Estimation window (default: 120 days)
- **CAR Windows**: Analysis windows (default: [1, 10, 30, 60, 90] days)
- **Scoring Weights**: Component weights (default: 25%, 20%, 25%, 15%, 15%)
- **Thresholds**: Volume spike, margin expansion, significance levels
- **Data Caching**: Cache directory and TTL

## Methodology

### Market Model
```
R_stock,t = α + β * R_market,t + ε_t
```
- Estimated using OLS on 120 trading days before announcement
- Used to calculate expected returns

### Abnormal Returns
```
AR_t = R_stock,t - (α + β * R_market,t)
```
- Daily abnormal return = actual return - expected return

### Cumulative Abnormal Returns
```
CAR(t1, t2) = Σ AR_t for t in [t1, t2]
```
- Sum of abnormal returns over window
- Statistical significance tested using t-tests

### Composite Score
```
Score = Σ (Normalized_Component_i * Weight_i)
```
- Each component normalized to 0-100 scale
- Weighted sum using configured weights
- Final score 0-100 with rating assignment

## Output Example

```
================================================================================
PEAD COMPOSITE SCORE REPORT
================================================================================

COMPOSITE SCORE: 73.45/100
RATING: BUY
CONFIDENCE: 85%

------------------------------------------------------------------------------

COMPONENT BREAKDOWN:

Earnings Surprise:
  Raw Score:             52.00
  Normalized (0-100):    74.29
  Weight:                25.0%
  Contribution:          18.57

Price Reaction:
  Raw Score:             14.00
  Normalized (0-100):    70.00
  Weight:                20.0%
  Contribution:          14.00

...

------------------------------------------------------------------------------

RECOMMENDATION:
STRONG PEAD SIGNAL - Score: 73.5/100. High probability of continued drift
in announcement direction. Consider entry for 30-60 day horizon.

================================================================================
```

## Performance Considerations

- **Caching**: All data fetched is cached (default 7 days TTL)
- **Parallel Fetching**: Independent data sources fetched concurrently
- **Fallback Logic**: Automatic fallback from NSE to Yahoo Finance
- **Error Handling**: Graceful degradation with partial data

## Limitations & Future Enhancements

### Current Limitations
- PDF parsing quality depends on document format
- Historical earnings consensus not available (using YoY/QoQ instead)
- Limited corporate governance data integration

### Planned Enhancements
- [ ] Backtesting framework with historical performance
- [ ] Portfolio construction with multiple signals
- [ ] Real-time monitoring and alerts
- [ ] Integration with trading APIs
- [ ] Machine learning model for score optimization
- [ ] More comprehensive fundamental data (Screener.in, etc.)

## Academic References

PEAD is well-documented in finance literature:

1. Ball, R., & Brown, P. (1968). "An Empirical Evaluation of Accounting Income Numbers"
2. Bernard, V., & Thomas, J. (1989). "Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?"
3. Chan, L. K., Jegadeesh, N., & Lakonishok, J. (1996). "Momentum Strategies"

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit pull request

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Email: [your-email]

## Disclaimer

This tool is for educational and research purposes only. Not financial advice.
Past performance does not guarantee future results. Always do your own research
and consult with qualified financial advisors before making investment decisions.

---

**Think like a quant. Trade like a professional. Built with ❤️ for the Indian markets.**
