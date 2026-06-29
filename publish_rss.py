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


def _load_episodes() -> list:
    if os.path.exists(EPISODES_DB):
        with open(EPISODES_DB) as f:
            return json.load(f)
    return []


def _save_episodes(episodes: list) -> None:
    os.makedirs("logs", exist_ok=True)
    with open(EPISODES_DB, "w") as f:
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


def _build_feed(episodes: list) -> str:
    image_block = ""
    if PODCAST_IMAGE_URL:
        image_block = f"""
    <itunes:image href="{_esc(PODCAST_IMAGE_URL)}" />
    <image>
      <url>{_esc(PODCAST_IMAGE_URL)}</url>
      <title>{_esc(PODCAST_TITLE)}</title>
      <link>{_esc(PODCAST_WEBSITE_URL)}</link>
    </image>"""

    items = "".join(_build_item(ep) for ep in reversed(episodes))

    return f"""<?xml version='1.0' encoding='UTF-8'?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{_esc(PODCAST_TITLE)}</title>
    <description>{_esc(PODCAST_DESCRIPTION)}</description>
    <language>{PODCAST_LANGUAGE}</language>
    <link>{_esc(PODCAST_WEBSITE_URL)}</link>
    <managingEditor>{_esc(PODCAST_EMAIL)} ({_esc(PODCAST_AUTHOR)})</managingEditor>
    <itunes:author>{_esc(PODCAST_AUTHOR)}</itunes:author>
    <itunes:email>{_esc(PODCAST_EMAIL)}</itunes:email>
    <itunes:category text="{_esc(PODCAST_CATEGORY)}" />
    <itunes:owner>
      <itunes:name>{_esc(PODCAST_AUTHOR)}</itunes:name>
      <itunes:email>{_esc(PODCAST_EMAIL)}</itunes:email>
    </itunes:owner>
    <itunes:explicit>false</itunes:explicit>{image_block}
{items}
  </channel>
</rss>"""


def update_feed(episode_title: str, audio_filename: str, audio_path: str,
                episode_number: int, script_excerpt: str) -> None:
    episodes = _load_episodes()
    now = datetime.now(timezone.utc)
    audio_url = f"{AUDIO_BASE_URL}/{audio_filename}" if AUDIO_BASE_URL else audio_filename

    # Avoid duplicate episodes
    if any(ep["number"] == episode_number for ep in episodes):
        print(f"[rss] Episode #{episode_number} already in feed, skipping")
        return

    episodes.append({
        "number":      episode_number,
        "title":       episode_title,
        "pubDate":     _rfc822(now),
        "guid":        f"aitechdaily-ep{episode_number}-{now.strftime('%Y%m%d')}",
        "description": script_excerpt[:500] + "...",
        "audio_url":   audio_url,
        "file_size":   os.path.getsize(audio_path) if os.path.exists(audio_path) else 0,
        "duration":    300,
    })

    # Sort newest first
    episodes.sort(key=lambda x: x["number"], reverse=True)

    _save_episodes(episodes)

    with open(RSS_FILE, "w", encoding="utf-8") as f:
        f.write(_build_feed(episodes))

    print(f"[rss] Feed updated -> {RSS_FILE}  (episode #{episode_number})")


def get_next_episode_number() -> int:
    episodes = _load_episodes()
    return max((ep["number"] for ep in episodes), default=0) + 1
