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


def analyze_articles_lexicon(articles: List[NewsArticle]) -> Dict[str, Any]:
    """Aggregate polarity → 0–100 score (50 = neutral)."""
    if not articles:
        return {
            "news_score_0_100": 50.0,
            "mean_polarity": 0.0,
            "mean_subjectivity": 0.0,
            "article_count": 0,
            "method": "textblob",
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
        "method": "textblob",
    }


def _llm_synthesis(
    symbol: str,
    company_name: str,
    articles: List[NewsArticle],
    max_items: int = 35,
) -> Optional[Dict[str, Any]]:
    api_key = CONFIG.get("OPENAI_API_KEY")
    if not api_key:
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


def run_news_sentiment_pipeline(
    symbol: str,
    company_name: str,
    articles: List[NewsArticle],
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
        combined = 0.45 * lex["news_score_0_100"] + 0.55 * llm_score
        out["news_score_0_100"] = float(max(0.0, min(100.0, combined)))
        out["method"] = "textblob+openai"
    else:
        out["news_score_0_100"] = lex["news_score_0_100"]
        out["method"] = "textblob"

    return out
