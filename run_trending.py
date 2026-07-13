# -*- coding: utf-8 -*-
"""
Trending-keyword SEO posts — publish ONE standalone blog post per top Google
trending search (default 3 per run; the workflow runs morning + evening, so
~6 keyword-targeted pages/day).

Why: the daily digest posts blend trends into one page, so no page targets a
trending query directly — impressions without clicks. These pages each chase
ONE exact query while it is spiking.

Posts render under the existing "Trending Now Daily" (world-news) section:
stored as logs/web/world-news/<YYYY-MM-DD>-<slug>.json, picked up by
generate_pages.build_web_posts — zero extra wiring.

Usage:
  python run_trending.py             # up to 3 new posts
  python run_trending.py --max 6
"""
import os, re, sys, json, time
from datetime import datetime, timezone
from email.utils import format_datetime

NICHE_ID  = "world-news"
SEEN_FILE = "logs/web/trending_seen.json"
MAX_POSTS = int(next((sys.argv[sys.argv.index("--max") + 1]
                      for a in sys.argv if a == "--max"), 3))

# Queries we never want a page for (thin/branded/unsafe intents)
SKIP_WORDS = {"porn", "nude", "leaked", "onlyfans", "xxx", "lottery numbers",
              "powerball numbers", "mega millions numbers", "wordle", "nyt connections",
              "quordle", "horoscope"}


def slugify(t, n=55):
    s = re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")
    return s[:n].rstrip("-") or "trend"


def _load_seen() -> list:
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_seen(seen: list):
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen[-400:], f, indent=1)


def _skippable(q: str) -> bool:
    ql = q.lower()
    return any(w in ql for w in SKIP_WORDS)


def main():
    from trends import fetch_trending
    from fetch_news import _google_news_search
    from generate_blog import generate_keyword_article

    trending = fetch_trending()
    if not trending:
        print("[trending] no trends available today — nothing to do")
        return

    seen = _load_seen()
    seen_set = {s.lower() for s in seen}
    date = datetime.now().strftime("%Y-%m-%d")
    posted = 0

    for t in trending:                      # already sorted by traffic desc
        if posted >= MAX_POSTS:
            break
        q = t["query"].strip()
        if len(q) < 3 or not q.isascii() or _skippable(q):
            continue
        if q.lower() in seen_set:
            continue

        slug = f"{date}-{slugify(q)}"
        path = f"logs/web/{NICHE_ID}/{slug}.json"
        if os.path.exists(path):
            seen.append(q); seen_set.add(q.lower())
            continue

        news = _google_news_search(q, max_items=5)
        if not news:                        # no coverage -> thin page, skip
            print(f"[trending] '{q}': no news coverage, skipping")
            continue

        try:
            art = generate_keyword_article(t, news)
        except Exception as e:
            print(f"[trending] '{q}' ERROR: {e}")
            continue
        if len(re.sub(r"<[^>]+>", " ", art["body_html"]).split()) < 400:
            print(f"[trending] '{q}': article too thin, skipping")
            continue

        art["headline"] = art["title"]
        art["slug"]     = slug
        art["date"]     = date
        art["pubDate"]  = format_datetime(datetime.now(timezone.utc))
        art["trend_query"] = q
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(art, f, indent=2)

        seen.append(q); seen_set.add(q.lower())
        posted += 1
        print(f"[trending] published {slug}")
        time.sleep(5)                       # be gentle on Groq free tier

    _save_seen(seen)
    print(f"\nTrending keyword posts published: {posted}")


if __name__ == "__main__":
    main()
