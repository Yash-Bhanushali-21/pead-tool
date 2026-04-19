"""
News sentiment: TextBlob on headlines/snippets + optional OpenAI JSON synthesis.

Set OPENAI_API_KEY for LLM layer; otherwise lexicon-only aggregate stands alone.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.config.config import CONFIG, config
from src.news.collector import NewsArticle
from src.news.digest_llm import run_news_ai_digest

logger = logging.getLogger(__name__)


def _textblob_scores(text: str) -> Dict[str, float]:
    try:
        from textblob import TextBlob

        tb = TextBlob(text)
        return {
            "polarity": float(tb.sentiment.polarity),
            "subjectivity": float(tb.sentiment.subjectivity),
        }
    except Exception as e:
        logger.warning(f"TextBlob failed: {e}")
        return {"polarity": 0.0, "subjectivity": 0.0}


def polarity_to_stance(polarity: float) -> str:
    """Map TextBlob polarity [-1, 1] to a discrete label."""
    if polarity >= 0.12:
        return "bullish"
    if polarity <= -0.12:
        return "bearish"
    return "neutral"


def score_to_stance(score_0_100: float) -> str:
    """Map aggregate 0–100 score to media stance (research label, not trading advice)."""
    if score_0_100 >= 58.0:
        return "bullish"
    if score_0_100 <= 42.0:
        return "bearish"
    return "neutral"


def analyze_articles_lexicon(articles: List[NewsArticle]) -> Dict[str, Any]:
    """Aggregate polarity → 0–100 score. No articles → no synthetic neutral score."""
    if not articles:
        return {
            "news_score_0_100": None,
            "mean_polarity": None,
            "mean_subjectivity": None,
            "article_count": 0,
            "lexicon_stance": "no_articles",
            "method": "textblob",
            "score_unavailable_reason": "no_headlines_collected",
        }

    pols, subs = [], []
    for a in articles:
        sc = _textblob_scores(a.text_for_sentiment())
        pols.append(sc["polarity"])
        subs.append(sc["subjectivity"])

    mp = sum(pols) / len(pols)
    ms = sum(subs) / len(subs)
    # Map polarity [-1,1] to [0,100]
    score = float((mp + 1.0) * 50.0)
    score = max(0.0, min(100.0, score))

    return {
        "news_score_0_100": score,
        "mean_polarity": mp,
        "mean_subjectivity": ms,
        "article_count": len(articles),
        "lexicon_stance": score_to_stance(score),
        "method": "textblob",
    }


def _llm_synthesis(
    symbol: str,
    company_name: str,
    articles: List[NewsArticle],
    max_items: int = 35,
) -> Optional[Dict[str, Any]]:
    api_key = CONFIG.get("OPENAI_API_KEY")
    if not api_key or not articles:
        return None

    lines = []
    for i, a in enumerate(articles[:max_items], 1):
        d = a.published.strftime("%Y-%m-%d") if a.published else "?"
        snippet = (a.summary or "")[:220].replace("\n", " ")
        lines.append(f"{i}. [{d}] {a.title} | {snippet}")

    body = "\n".join(lines)
    prompt = f"""You are an equity research assistant. Below are recent news headlines/snippets about {company_name} (NSE: {symbol}).

Infer overall media tone toward the company (not a buy/sell recommendation).

Return ONLY valid JSON with keys:
- "overall": one of "bullish", "neutral", "bearish"
- "confidence": number 0 to 1
- "themes": array of up to 5 short strings (topics repeated in coverage)
- "watch_items": array of up to 3 risk or catalyst strings mentioned in headlines
- "one_line": single sentence summary for a trader's notebook

News items:
{body}
"""

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=config.OPENAI_NEWS_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Reply with JSON only. No markdown fences.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=700,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1] if len(parts) >= 2 else raw
            if raw.lstrip().startswith("json"):
                raw = raw.lstrip()[4:].lstrip()
        import re as _re

        m = _re.search(r"\{[\s\S]*\}", raw)
        if m:
            raw = m.group(0)
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"OpenAI news synthesis failed: {e}")
        return None


def _map_llm_to_score(llm: Dict[str, Any]) -> float:
    o = (llm.get("overall") or "neutral").lower()
    conf = float(llm.get("confidence") or 0.5)
    base = 50.0
    if "bull" in o:
        base = 72.0
    elif "bear" in o:
        base = 28.0
    else:
        base = 50.0
    # Pull toward 50 if low confidence
    return base * conf + 50.0 * (1.0 - conf)


def per_article_lexicon(articles: List[NewsArticle], limit: int = 80) -> List[Dict[str, Any]]:
    """Per-article polarity + stance for transparency (research only)."""
    rows: List[Dict[str, Any]] = []
    for a in articles[:limit]:
        sc = _textblob_scores(a.text_for_sentiment())
        pol = sc["polarity"]
        rows.append(
            {
                "title": a.title[:200],
                "url": a.url,
                "source": a.source,
                "published": a.published.strftime("%Y-%m-%d") if a.published else None,
                "polarity": round(pol, 4),
                "stance": polarity_to_stance(pol),
                "has_body": bool((a.body_text or "").strip()),
                "scrape_ok": a.scrape_error is None and bool((a.body_text or "").strip()),
                "scrape_error": a.scrape_error,
                "metadata": {
                    k: v
                    for k, v in (a.scrape_metadata or {}).items()
                    if k in ("hostname", "sitename", "author", "date", "word_count")
                },
            }
        )
    return rows


def run_news_sentiment_pipeline(
    symbol: str,
    company_name: str,
    articles: List[NewsArticle],
    *,
    include_ai_digest: bool = True,
) -> Dict[str, Any]:
    """
    Lexicon aggregate + optional LLM narrative; combined score when LLM present.
    """
    lex = analyze_articles_lexicon(articles)
    llm = _llm_synthesis(symbol, company_name, articles)

    out = {
        **lex,
        "article_count": len(articles),
        "llm": llm,
        "openai_used": llm is not None,
    }

    if llm:
        llm_score = _map_llm_to_score(llm)
        lx = lex.get("news_score_0_100")
        if lx is not None:
            combined = 0.45 * float(lx) + 0.55 * llm_score
            out["news_score_0_100"] = float(max(0.0, min(100.0, combined)))
        else:
            out["news_score_0_100"] = float(max(0.0, min(100.0, llm_score)))
        out["method"] = "textblob+openai"
        overall = (llm.get("overall") or "neutral").lower()
        if "bull" in overall:
            out["llm_stance"] = "bullish"
        elif "bear" in overall:
            out["llm_stance"] = "bearish"
        else:
            out["llm_stance"] = "neutral"
    else:
        out["news_score_0_100"] = lex["news_score_0_100"]
        out["method"] = "textblob"
        out["llm_stance"] = None

    ns = out.get("news_score_0_100")
    if ns is not None:
        out["stock_media_stance"] = score_to_stance(float(ns))
        score_part = f"score {float(ns):.1f}/100"
    else:
        out["stock_media_stance"] = "no_score"
        score_part = "score unavailable (no headline sample)"
    out["stance_summary"] = (
        f"Aggregate media tone: {out['stock_media_stance']} "
        f"({score_part}; lexicon {lex.get('lexicon_stance', 'n/a')}"
        + (f", LLM {out.get('llm_stance')}" if out.get("llm_stance") else "")
        + "). Research context only — not a buy/sell recommendation."
    )
    out["per_article"] = per_article_lexicon(articles)
    out["disclaimer"] = (
        "Media sentiment is noisy and incomplete; many articles are headlines only or blocked from scraping. "
        "Not investment advice."
    )

    if include_ai_digest:
        digest = run_news_ai_digest(symbol, company_name, articles, out)
        if digest:
            out["ai_digest"] = digest
            out["ai_digest_used"] = True
        else:
            out["ai_digest"] = None
            out["ai_digest_used"] = False
    else:
        out["ai_digest"] = None
        out["ai_digest_used"] = False
        out["ai_digest_skipped_by_request"] = True

    return out
