"""
Step 4 — Maintain the RSS 2.0 feed XML file.
Uses string-based XML building to avoid Python ElementTree namespace issues.
"""

import os
import json
from datetime import datetime, timezone
from config import (
    PODCAST_TITLE, PODCAST_DESCRIPTION, PODCAST_AUTHOR,
    PODCAST_EMAIL, PODCAST_LANGUAGE, PODCAST_CATEGORY,
    PODCAST_IMAGE_URL, PODCAST_WEBSITE_URL, RSS_FILE,
)

AUDIO_BASE_URL = PODCAST_WEBSITE_URL.rstrip("/") + "/episodes" if PODCAST_WEBSITE_URL else ""
EPISODES_DB    = "logs/episodes.json"


def _rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


def _db_path(rss_file: str = None) -> str:
    """Each niche gets its own episode DB derived from its RSS filename."""
    if rss_file and rss_file != RSS_FILE:
        base = os.path.splitext(os.path.basename(rss_file))[0]
        return f"logs/episodes_{base}.json"
    return EPISODES_DB


def _load_episodes(rss_file: str = None) -> list:
    path = _db_path(rss_file)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def _save_episodes(episodes: list, rss_file: str = None) -> None:
    os.makedirs("logs", exist_ok=True)
    with open(_db_path(rss_file), "w") as f:
        json.dump(episodes, f, indent=2)


def _build_item(ep: dict) -> str:
    return f"""
    <item>
      <title>{_esc(ep['title'])}</title>
      <pubDate>{ep['pubDate']}</pubDate>
      <guid isPermaLink="false">{_esc(ep['guid'])}</guid>
      <description>{_esc(ep['description'])}</description>
      <itunes:episode>{ep['number']}</itunes:episode>
      <itunes:duration>{ep['duration']}</itunes:duration>
      <enclosure url="{_esc(ep['audio_url'])}" type="audio/mpeg" length="{ep['file_size']}" />
    </item>"""


def _build_feed(episodes: list, title=None, description=None, author=None, category=None, image_url=None) -> str:
    title       = title       or PODCAST_TITLE
    description = description or PODCAST_DESCRIPTION
    author      = author      or PODCAST_AUTHOR
    category    = category    or PODCAST_CATEGORY
    image_url   = image_url   or PODCAST_IMAGE_URL
    image_block = ""
    if image_url:
        image_block = f"""
    <itunes:image href="{_esc(image_url)}" />
    <image>
      <url>{_esc(image_url)}</url>
      <title>{_esc(title)}</title>
      <link>{_esc(PODCAST_WEBSITE_URL)}</link>
    </image>"""

    items = "".join(_build_item(ep) for ep in reversed(episodes))

    return f"""<?xml version='1.0' encoding='UTF-8'?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{_esc(title)}</title>
    <description>{_esc(description)}</description>
    <language>{PODCAST_LANGUAGE}</language>
    <link>{_esc(PODCAST_WEBSITE_URL)}</link>
    <managingEditor>{_esc(PODCAST_EMAIL)} ({_esc(author)})</managingEditor>
    <itunes:author>{_esc(author)}</itunes:author>
    <itunes:email>{_esc(PODCAST_EMAIL)}</itunes:email>
    <itunes:category text="{_esc(category)}" />
    <itunes:owner>
      <itunes:name>{_esc(author)}</itunes:name>
      <itunes:email>{_esc(PODCAST_EMAIL)}</itunes:email>
    </itunes:owner>
    <itunes:explicit>false</itunes:explicit>{image_block}
{items}
  </channel>
</rss>"""


def update_feed(episode_title: str, audio_filename: str, audio_path: str,
                episode_number: int, script_excerpt: str,
                rss_file: str = None, audio_base_url: str = None,
                niche: dict = None) -> None:
    # Support per-niche overrides
    _rss_file  = rss_file or RSS_FILE
    _audio_url = f"{audio_base_url}/{audio_filename}" if audio_base_url else f"{AUDIO_BASE_URL}/{audio_filename}"
    _niche_id  = niche["id"] if niche else "ai-tech"
    _db_file   = f"logs/episodes_{_niche_id}.json"

    # Load per-niche episode DB
    episodes = []
    if os.path.exists(_db_file):
        with open(_db_file) as f:
            episodes = json.load(f)

    now = datetime.now(timezone.utc)

    if any(ep["number"] == episode_number for ep in episodes):
        print(f"[rss] Episode #{episode_number} already in feed for {_niche_id}, skipping")
        return

    episodes.append({
        "number":      episode_number,
        "title":       episode_title,
        "pubDate":     _rfc822(now),
        "guid":        f"{_niche_id}-ep{episode_number}-{now.strftime('%Y%m%d')}",
        "description": script_excerpt[:500] + "...",
        "audio_url":   _audio_url,
        "file_size":   os.path.getsize(audio_path) if os.path.exists(audio_path) else 0,
        "duration":    300,
    })
    episodes.sort(key=lambda x: x["number"], reverse=True)

    os.makedirs("logs", exist_ok=True)
    with open(_db_file, "w") as f:
        json.dump(episodes, f, indent=2)

    # Build niche-specific feed metadata
    feed_title  = niche["title"]       if niche else PODCAST_TITLE
    feed_desc   = niche["description"] if niche else PODCAST_DESCRIPTION
    feed_author = niche["author"]      if niche else PODCAST_AUTHOR
    feed_cat    = niche["category"]    if niche else PODCAST_CATEGORY
    feed_image  = niche.get("cover_url", PODCAST_IMAGE_URL) if niche else PODCAST_IMAGE_URL

    os.makedirs(os.path.dirname(_rss_file) if os.path.dirname(_rss_file) else ".", exist_ok=True)
    with open(_rss_file, "w", encoding="utf-8") as f:
        f.write(_build_feed(episodes, feed_title, feed_desc, feed_author, feed_cat, feed_image))

    print(f"[rss] Feed updated -> {_rss_file}  (episode #{episode_number})")


def get_next_episode_number(rss_file: str = None, niche: dict = None) -> int:
    if niche:
        niche_id = niche["id"]
    elif rss_file and rss_file != RSS_FILE:
        niche_id = os.path.splitext(os.path.basename(rss_file))[0]
    else:
        niche_id = "ai-tech"
    db = f"logs/episodes_{niche_id}.json"
    if not os.path.exists(db):
        return 1
    with open(db) as f:
        episodes = json.load(f)
    return max((ep["number"] for ep in episodes), default=0) + 1
