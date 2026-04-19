from src.news.collector import NewsCollector, NewsArticle
from src.news.sentiment_pipeline import run_news_sentiment_pipeline

# Note: ``run_news_sentiment_layer`` lives in ``src.news.layer`` — import it from there
# to avoid circular imports (stock_analyzer → news → layer → stock_analyzer).

__all__ = ["NewsCollector", "NewsArticle", "run_news_sentiment_pipeline"]
