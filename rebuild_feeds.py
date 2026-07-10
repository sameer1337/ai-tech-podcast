"""Rebuild all RSS feeds with correct cover art URLs."""
import os, json
from publish_rss import _build_feed, PODCAST_EMAIL, PODCAST_LANGUAGE, PODCAST_WEBSITE_URL
from niches import PODCASTS

BASE = "https://sameer1337.github.io/ai-tech-podcast"

COVERS = {
    "ai-tech":    "assets/cover.png",
    "finance":    "assets/cover_finance.png",
    "health":     "assets/cover_health.png",
    "startup":    "assets/cover_startup.png",
    "crypto":     "assets/cover_crypto.png",
    "world-news": "assets/cover_trending.png",
    "true-crime": "assets/cover_truecrime.png",
}

for niche in PODCASTS:
    pid = niche["id"]
    db  = f"logs/episodes_{pid}.json"
    if not os.path.exists(db):
        print(f"[skip] No episodes for {pid}")
        continue

    with open(db) as f:
        episodes = json.load(f)

    rss = niche["rss_file"]
    os.makedirs(os.path.dirname(rss) if os.path.dirname(rss) else ".", exist_ok=True)

    cover = f"{BASE}/{COVERS.get(pid, 'assets/cover.png')}"
    with open(rss, "w", encoding="utf-8") as f:
        f.write(_build_feed(episodes, niche["title"], niche["description"],
                            niche["author"], niche["category"], cover))
    print(f"[rss] Rebuilt {rss} for {pid}")
