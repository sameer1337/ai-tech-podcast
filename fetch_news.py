"""
Step 1 — Fetch top AI/tech stories from RSS feeds.
Returns a list of dicts: {title, url, summary, source, published}.
"""

import os
import json
import re
import feedparser
import httpx
from datetime import datetime, timezone, timedelta
from config import RSS_FEEDS, MAX_ITEMS_PER_FEED, TOP_STORIES

# ── Cross-day story memory ─────────────────────────────────────────────────
# Big stories sit at the top of RSS feeds for days. Without memory, the same
# story leads several consecutive episodes → duplicate titles + repeated
# content. Selected stories are remembered here (committed via logs/) and
# blocked for SEEN_DAYS.
SEEN_FILE = "logs/seen_stories.json"
SEEN_DAYS = 7

# Recurring meta-digest articles (same headline every day, no specific story)
DIGEST_PATTERNS = re.compile(
    r"here'?s what happened|news roundup|daily digest|week in review"
    r"|everything you need to know|top \d+ stories|weekly recap",
    re.IGNORECASE,
)


def _story_key(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower())[:60].strip()


def _load_seen(niche_id: str) -> dict:
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            all_seen = json.load(f)
    except Exception:
        return {}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEEN_DAYS)).strftime("%Y-%m-%d")
    return {k: d for k, d in all_seen.get(niche_id, {}).items() if d >= cutoff}


def _mark_seen(niche_id: str, stories: list):
    all_seen = {}
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, encoding="utf-8") as f:
                all_seen = json.load(f)
        except Exception:
            pass
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    niche_seen = _load_seen(niche_id)  # already pruned to SEEN_DAYS
    for s in stories:
        niche_seen[_story_key(s["title"])] = today
    all_seen[niche_id] = niche_seen
    os.makedirs("logs", exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(all_seen, f, indent=1)


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


# Only filter hyper-local Pakistani city/provincial news — not country-level world news
REGIONAL_FILTER = {
    "karachi", "lahore", "islamabad", "rawalpindi", "peshawar",
    "punjab cm", "sindh cm", "pti rally", "imran khan arrested",
    "pakistan rupee", "pakistan cricket",
}

def _fetch(feeds: list, keywords: list, max_per_feed: int = 8, top_n: int = 5,
           regional_filter: bool = True, niche_id: str = None) -> list[dict]:
    kw_set = set(keywords)
    stories = []

    # What is the world searching for today? (fails safe to [])
    try:
        from trends import fetch_trending, trend_boost
        trending = fetch_trending()
    except Exception:
        trending = []

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get("title", url)
            for entry in feed.entries[:max_per_feed]:
                title   = (entry.get("title") or "").lower()
                summary = (entry.get("summary") or entry.get("description") or "").lower()
                text    = title + " " + summary

                # Only filter very local Pakistani news
                if regional_filter and any(region in text for region in REGIONAL_FILTER):
                    continue

                # Skip recurring meta-digest headlines (recur daily, no story)
                if DIGEST_PATTERNS.search(entry.get("title", "")):
                    continue

                score   = sum(1 for kw in kw_set if kw in text)

                # Google Trends boost: stories people are searching for
                # today outrank everything else
                trend_q = ""
                if trending:
                    tb, trend_q = trend_boost(entry.get("title", ""),
                                              entry.get("summary", "") or "",
                                              trending)
                    score += tb

                published = entry.get("published_parsed")
                if published:
                    try:
                        age_h = (datetime.now(timezone.utc) - datetime(*published[:6], tzinfo=timezone.utc)).total_seconds() / 3600
                        if age_h < 24:
                            score += 3
                    except Exception:
                        pass

                stories.append({
                    "title":     entry.get("title", ""),
                    "url":       entry.get("link", ""),
                    "summary":   entry.get("summary", entry.get("description", "")),
                    "source":    source,
                    "published": entry.get("published", ""),
                    "_score":    score,
                    "_trend":    trend_q,
                })
        except Exception as e:
            print(f"[fetch] Warning: could not parse {url}: {e}")

    seen, unique = set(), []
    for s in stories:
        key = s["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    unique.sort(key=lambda x: x["_score"], reverse=True)

    # Cross-day dedupe: drop stories already covered in the last SEEN_DAYS
    if niche_id:
        seen = _load_seen(niche_id)
        fresh = [s for s in unique if _story_key(s["title"]) not in seen]
        skipped = len(unique) - len(fresh)
        if skipped:
            print(f"[fetch] Skipped {skipped} stories already covered this week")
        # Fallback: if feeds are stale and almost nothing is new, top up with
        # seen stories rather than producing an empty episode
        if len(fresh) < 2:
            print("[fetch] WARNING: <2 fresh stories - topping up with covered ones")
            fresh += [s for s in unique if s not in fresh]
        unique = fresh

    top = unique[:top_n]
    if niche_id and top:
        _mark_seen(niche_id, top)

    print(f"[fetch] Selected {len(top)} stories from {len(stories)} fetched")
    for i, s in enumerate(top, 1):
        flag = f"  ** TRENDING: '{s['_trend']}'" if s.get("_trend") else ""
        print(f"  {i}. {s['title']} [{s['source']}]{flag}")
    return top


def fetch_stories() -> list[dict]:
    """Original single-niche fetch (used by run_daily.py)."""
    return _fetch(RSS_FEEDS, list(AI_KEYWORDS), MAX_ITEMS_PER_FEED, TOP_STORIES)


def fetch_stories_for_niche(niche: dict) -> list[dict]:
    """Fetch stories for a specific niche config from niches.py."""
    return _fetch(niche["feeds"], niche.get("keywords", []),
                  max_per_feed=10, top_n=TOP_STORIES, regional_filter=True,
                  niche_id=niche["id"])


AI_KEYWORDS = {
    "ai", "artificial intelligence", "llm", "gpt", "model", "openai",
    "google", "microsoft", "apple", "meta", "nvidia", "chip", "robot",
    "automation", "startup", "funding", "launch", "release", "feature",
}

if __name__ == "__main__":
    fetch_stories()
