"""
Generate Alexa Flash Briefing feeds (JSON) for each niche.

Alexa Flash Briefing skills read a simple JSON feed and play the newest item
when a user says "Alexa, what's the news?" / "play my Flash Briefing". A daily
5-minute news show is the ideal Flash Briefing format.

Output: flash/<niche-id>.json  (served by GitHub Pages, e.g.
        https://sameer1337.github.io/ai-tech-podcast/flash/startup.json)

Submit each JSON URL as a NEW Flash Briefing skill at developer.amazon.com:
  Alexa Skills > Create Skill > Flash Briefing > add content feed (Audio).

Spec notes:
- Newest item first; Alexa reads the most recent entries.
- updateDate must be ISO-8601 UTC ending in ".0Z".
- streamUrl must be public HTTPS audio (GitHub Pages qualifies). We use the
  direct .mp3 URL (not the Podtrac redirect) so Alexa's player never has to
  follow a 302 mid-stream.
"""

import os
import json
from email.utils import parsedate_to_datetime

from niches import PODCASTS

FLASH_DIR   = "flash"
MAX_ITEMS   = 5  # how many recent episodes to expose in the briefing feed
SITE_URL    = "https://sameer1337.github.io/ai-tech-podcast"


def _db_path(niche: dict) -> str:
    return f"logs/episodes_{niche['id']}.json"


def _iso_update_date(rfc822: str) -> str:
    """Convert an RFC-822 pubDate to the ISO-8601 form Alexa expects."""
    dt = parsedate_to_datetime(rfc822)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.0Z")


def build_feed(niche: dict) -> list | None:
    db = _db_path(niche)
    if not os.path.exists(db):
        print(f"[flash] no episodes for {niche['id']}, skipping")
        return None

    with open(db, encoding="utf-8") as f:
        episodes = json.load(f)

    # newest first
    episodes = sorted(episodes, key=lambda e: e["number"], reverse=True)[:MAX_ITEMS]

    items = []
    for ep in episodes:
        items.append({
            "uid":            ep["guid"],
            "updateDate":     _iso_update_date(ep["pubDate"]),
            "titleText":      ep["title"],
            "streamUrl":      ep["audio_url"],          # direct HTTPS .mp3
            "redirectionUrl": SITE_URL,
        })
    return items


def build_all() -> None:
    os.makedirs(FLASH_DIR, exist_ok=True)
    built = 0
    for niche in PODCASTS:
        feed = build_feed(niche)
        if not feed:
            continue
        out = os.path.join(FLASH_DIR, f"{niche['id']}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(feed, f, indent=2)
        print(f"[flash] {out}  ({len(feed)} items)  -> {SITE_URL}/{FLASH_DIR}/{niche['id']}.json")
        built += 1
    print(f"[flash] done, {built} briefing feeds written")


if __name__ == "__main__":
    build_all()
