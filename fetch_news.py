"""
Step 1 — Fetch top AI/tech stories from RSS feeds.
Returns a list of dicts: {title, url, summary, source, published}.
"""

import feedparser
import httpx
from datetime import datetime, timezone
from config import RSS_FEEDS, MAX_ITEMS_PER_FEED, TOP_STORIES


def _score(entry) -> float:
    """Simple relevance score — prefer fresh items with AI/tech keywords."""
    AI_KEYWORDS = {
        "ai", "artificial intelligence", "llm", "gpt", "model", "openai",
        "google", "microsoft", "apple", "meta", "nvidia", "chip", "robot",
        "automation", "startup", "funding", "launch", "release", "feature",
    }
    title = (entry.get("title") or "").lower()
    summary = (entry.get("summary") or "").lower()
    text = title + " " + summary
    score = sum(1 for kw in AI_KEYWORDS if kw in text)

    # freshness bonus (items from last 24 h get +3)
    published = entry.get("published_parsed")
    if published:
        age_h = (datetime.now(timezone.utc) - datetime(*published[:6], tzinfo=timezone.utc)).total_seconds() / 3600
        if age_h < 24:
            score += 3
    return score


def fetch_stories() -> list[dict]:
    stories = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get("title", url)
            for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
                stories.append({
                    "title":     entry.get("title", ""),
                    "url":       entry.get("link", ""),
                    "summary":   entry.get("summary", entry.get("description", "")),
                    "source":    source,
                    "published": entry.get("published", ""),
                    "_score":    _score(entry),
                })
        except Exception as e:
            print(f"[fetch] Warning: could not parse {url}: {e}")

    # deduplicate by title (first 60 chars)
    seen, unique = set(), []
    for s in stories:
        key = s["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    # sort by score and take the top N
    unique.sort(key=lambda x: x["_score"], reverse=True)
    top = unique[:TOP_STORIES]

    print(f"[fetch] Selected {len(top)} stories from {len(stories)} fetched")
    for i, s in enumerate(top, 1):
        print(f"  {i}. {s['title']} [{s['source']}]")

    return top


if __name__ == "__main__":
    fetch_stories()
