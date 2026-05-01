export interface ToolsConfig {
  cli_equivalent?: {
    modes?: string[];
    flags?: string[];
  };
  news?: {
    lookback_days_default?: number;
    max_articles_default?: number;
    max_scrape_default?: number;
    openai_news_model?: string;
    extra_rss_feeds_configured?: number;
    news_ai_digest_enabled?: boolean;
    openai_news_digest_model?: string | null;
    newsapi_configured?: boolean;
    news_google_chunk_threshold_days?: number;
    news_html_discovery_enabled?: boolean;
    news_html_discovery_max_total?: number;
    exchange_announcements_enabled?: boolean;
    news_dedup_title_enabled?: boolean;
  };
  technical?: {
    openai_tech_verdict_model?: string;
  };
  market_model?: {
    estimation_window_days?: number;
    market_index?: string;
    min_trading_days?: number;
  };
  car_windows_days?: number[];
  significance_level?: number;
  paths?: {
    output_default?: string;
    pdf_download_dir?: string;
    cache_dir?: string;
  };
  equity_pipeline_stages?: string[];
}
