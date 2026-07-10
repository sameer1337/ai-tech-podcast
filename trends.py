"""
Google Trends awareness for story ranking.

Google has no official public Trends API (the unofficial pytrends library is
rate-limited heavily from CI IPs), but the official trending-searches RSS is
stable and free:  https://trends.google.com/trending/rss?geo=US

Each entry gives the trending query, approximate search traffic, and the news
headline driving the trend. Stories that match a trending query (or its news
headline) get a large score boost in fetch_news, so what people are actually
searching for today leads the episode - and the Short.

Fails safe: any error returns an empty list and ranking proceeds untouched.
"""

import os
import re
import json
from datetime import datetime, timezone

TRENDS_GEOS = ("US", "GB")
CACHE_FILE = "logs/trends_cache.json"

STOPWORDS = {
    "the", "a", "an", "of", "in", "and", "to", "for", "on", "at", "as", "is",
    "are", "was", "with", "by", "from", "its", "his", "her", "how", "why",
    "what", "who", "new", "says", "said", "after", "over", "amid", "vs",
}


def _tokens(text: str) -> set:
    words = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split()
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def _parse_traffic(raw: str) -> int:
    """'500+' -> 500, '1M+' -> 1000000, '20K+' -> 20000."""
    m = re.match(r"([\d.]+)\s*([KM]?)", str(raw).strip().upper())
    if not m:
        return 0
    n = float(m.group(1))
    return int(n * {"": 1, "K": 1_000, "M": 1_000_000}[m.group(2)])


def fetch_trending() -> list[dict]:
    """Return today's trending searches: [{query, traffic, news, tokens...}].
    Cached per UTC day (logs/ is committed, so CI reuses it within a day)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("date") == today and cache.get("trends"):
                return cache["trends"]
        except Exception:
            pass

    trends, seen = [], set()
    try:
        import feedparser
        for geo in TRENDS_GEOS:
            feed = feedparser.parse(f"https://trends.google.com/trending/rss?geo={geo}")
            for e in feed.entries:
                query = (e.get("title") or "").strip()
                if not query or query.lower() in seen:
                    continue
                seen.add(query.lower())
                trends.append({
                    "query":   query,
                    "traffic": _parse_traffic(e.get("ht_approx_traffic", "0")),
                    "news":    str(e.get("ht_news_item_title", "") or ""),
                })
    except Exception as ex:
        print(f"[trends] fetch failed ({ex}) - ranking without trend boost")
        return []

    trends.sort(key=lambda t: t["traffic"], reverse=True)
    try:
        os.makedirs("logs", exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": today, "trends": trends}, f, indent=1)
    except Exception:
        pass
    print(f"[trends] {len(trends)} trending searches loaded")
    return trends


def trend_boost(title: str, summary: str, trends: list) -> tuple:
    """Return (boost, matched_query). A story matches when every significant
    token of the trending query appears in it, or when it heavily overlaps
    the trend's driving news headline."""
    story_toks = _tokens(title + " " + summary)
    if not story_toks:
        return 0, ""
    for t in trends:
        q_toks = _tokens(t["query"])
        if q_toks and q_toks <= story_toks:
            traffic = t["traffic"]
            boost = 10 if traffic >= 1_000_000 else 8 if traffic >= 100_000 \
                else 7 if traffic >= 10_000 else 6
            return boost, t["query"]
        n_toks = _tokens(t["news"])
        if len(n_toks) >= 4:
            overlap = len(n_toks & story_toks) / len(n_toks)
            if overlap >= 0.6:
                return 5, t["query"]
    return 0, ""


if __name__ == "__main__":
    for t in fetch_trending()[:15]:
        print(f"{t['traffic']:>9,}  {t['query']}  <- {t['news'][:50]}")
