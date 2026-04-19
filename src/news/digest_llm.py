"""
Post-aggregation LLM digest: rationale + key points over the full headline set (research-only).

Requires ``OPENAI_API_KEY``. Controlled by ``NEWS_AI_DIGEST_ENABLED`` and ``OPENAI_NEWS_DIGEST_MODEL``.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.config.config import CONFIG
from src.news.collector import NewsArticle

logger = logging.getLogger(__name__)


def run_news_ai_digest(
    symbol: str,
    company_name: str,
    articles: List[NewsArticle],
    pipeline_out: Dict[str, Any],
    *,
    max_headlines: int = 45,
) -> Optional[Dict[str, Any]]:
    """
    Produce a structured digest: multi-sentence rationale, key points, and how they relate to tone.

    ``pipeline_out`` is the dict returned so far from ``run_news_sentiment_pipeline`` (lexicon + optional ``llm``).
    """
    if not CONFIG.get("NEWS_AI_DIGEST_ENABLED", True):
        return None
    api_key = CONFIG.get("OPENAI_API_KEY")
    if not api_key or not articles:
        return None

    model = CONFIG.get("OPENAI_NEWS_DIGEST_MODEL") or CONFIG.get("OPENAI_NEWS_MODEL") or "gpt-4o-mini"

    lines: List[str] = []
    for i, a in enumerate(articles[:max_headlines], 1):
        d = a.published.strftime("%Y-%m-%d") if a.published else "?"
        snip = (a.summary or "")[:180].replace("\n", " ")
        lines.append(f"{i}. [{a.source}] [{d}] {a.title} | {snip}")

    lex = {
        "news_score_0_100": pipeline_out.get("news_score_0_100"),
        "mean_polarity": pipeline_out.get("mean_polarity"),
        "lexicon_stance": pipeline_out.get("lexicon_stance"),
        "stock_media_stance": pipeline_out.get("stock_media_stance"),
        "method": pipeline_out.get("method"),
    }
    prior_llm = pipeline_out.get("llm") if isinstance(pipeline_out.get("llm"), dict) else None

    prompt = f"""You are a senior equity research assistant (India markets). You are given headlines/snippets
about **{company_name}** (ticker context: {symbol}) and aggregate sentiment stats (not investment advice).

Prior structured synthesis (may be null): {json.dumps(prior_llm, ensure_ascii=False)[:3500]}
Aggregate stats (JSON): {json.dumps(lex, ensure_ascii=False)}

Headlines (truncated; order is recency-biased):
{chr(10).join(lines)}

Return ONLY valid JSON with these keys:
- "rationale": array of **5 to 6** short strings — each one complete sentence: why the overall media tone
  (bullish/neutral/bearish) is plausible from these headlines, what is **not** proven by them, and major themes.
- "key_points": array of **6 to 10** bullet strings — concrete facts or claims **explicitly tied** to specific
  story angles (e.g. regulation, sector, macro, company action). Use neutral wording; cite themes, not price targets.
- "tone_alignment": one paragraph (3-4 sentences max) explaining how the headline mix supports or contradicts
  the aggregate score/stance.
- "limitations": one paragraph on data gaps (RSS bias, missing dates, paywalls, non-English coverage, etc.).

Rules: No buy/sell language. No fabricated tickers or events not implied by the list. If headlines are thin,
say so in limitations and shorten key_points accordingly.
"""

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Reply with JSON only. No markdown fences. Be concise and skeptical.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
            max_tokens=1100,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1] if len(parts) >= 2 else raw
            if raw.lstrip().startswith("json"):
                raw = raw.lstrip()[4:].lstrip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            raw = m.group(0)
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        parsed["model"] = model
        parsed["disclaimer"] = (
            "AI-generated digest over incomplete RSS/snippet data — research context only, not advice."
        )
        return parsed
    except Exception as e:
        logger.warning("OpenAI news digest failed: %s", e)
        return None
