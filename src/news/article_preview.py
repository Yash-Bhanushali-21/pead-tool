"""Build API/UI preview rows from collected articles (ordering friendly to undated discovery hits)."""
from __future__ import annotations

from typing import Any, Dict, List

from src.news.collector import NewsArticle


def build_article_preview_rows(articles: List[NewsArticle], preview_limit: int) -> List[Dict[str, Any]]:
    """
    Prefer **dated** articles (newest first), then **undated** (e.g. HTML search discovery, DDG lite)
    so preview/citations lists are not dominated only by RSS-dated items when the cap is tight.
    """
    cap = max(0, int(preview_limit))
    if cap <= 0 or not articles:
        return []

    dated = [a for a in articles if a.published is not None]
    undated = [a for a in articles if a.published is None]
    dated.sort(key=lambda a: a.published, reverse=True)  # type: ignore[arg-type, union-attr]
    ordered = dated + undated

    out: List[Dict[str, Any]] = []
    seen_url: set[str] = set()
    for a in ordered:
        if len(out) >= cap:
            break
        if a.url in seen_url:
            continue
        seen_url.add(a.url)
        row: Dict[str, Any] = {
            "title": a.title,
            "url": a.url,
            "published": a.published.isoformat() if a.published else None,
            "source": a.source,
            "summary": (a.summary or "")[:1200],
        }
        if (a.body_text or "").strip():
            row["body_preview"] = (a.body_text[:900] + "…") if len(a.body_text) > 900 else a.body_text
            row["body_word_count"] = len(a.body_text.split())
        if a.scrape_metadata:
            row["page_metadata"] = {
                k: v
                for k, v in a.scrape_metadata.items()
                if k
                in (
                    "title",
                    "author",
                    "hostname",
                    "sitename",
                    "date",
                    "description",
                    "word_count",
                )
            }
        if a.scrape_error:
            row["scrape_error"] = a.scrape_error[:200]
        out.append(row)
    return out
