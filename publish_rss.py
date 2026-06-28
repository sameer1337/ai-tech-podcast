"""
Step 4 — Maintain the RSS 2.0 feed XML file.
This feed is hosted on GitHub Pages and submitted once to each podcast platform.
Platforms poll it daily to pick up new episodes automatically.
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from config import (
    PODCAST_TITLE, PODCAST_DESCRIPTION, PODCAST_AUTHOR,
    PODCAST_EMAIL, PODCAST_LANGUAGE, PODCAST_CATEGORY,
    PODCAST_IMAGE_URL, PODCAST_WEBSITE_URL, RSS_FILE,
)

# GitHub Pages base URL for audio files — set this after deploying
# e.g. "https://yourusername.github.io/ai-tech-podcast/episodes"
AUDIO_BASE_URL = PODCAST_WEBSITE_URL.rstrip("/") + "/episodes" if PODCAST_WEBSITE_URL else ""


def _get_file_size_mb(path: str) -> int:
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0


def _rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def update_feed(episode_title: str, audio_filename: str, audio_path: str,
                episode_number: int, script_excerpt: str) -> None:
    """Add a new episode to the RSS feed XML."""

    # Load existing feed or create fresh
    if os.path.exists(RSS_FILE):
        tree = ET.parse(RSS_FILE)
        root = tree.getroot()
        channel = root.find("channel")
    else:
        root = ET.Element("rss", {
            "version": "2.0",
            "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
            "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
        })
        channel = ET.SubElement(root, "channel")

        ET.SubElement(channel, "title").text = PODCAST_TITLE
        ET.SubElement(channel, "description").text = PODCAST_DESCRIPTION
        ET.SubElement(channel, "language").text = PODCAST_LANGUAGE
        ET.SubElement(channel, "link").text = PODCAST_WEBSITE_URL
        ET.SubElement(channel, "itunes:author").text = PODCAST_AUTHOR
        ET.SubElement(channel, "itunes:category", {"text": PODCAST_CATEGORY})
        if PODCAST_IMAGE_URL:
            img = ET.SubElement(channel, "itunes:image")
            img.set("href", PODCAST_IMAGE_URL)

        owner = ET.SubElement(channel, "itunes:owner")
        ET.SubElement(owner, "itunes:name").text = PODCAST_AUTHOR
        ET.SubElement(owner, "itunes:email").text = PODCAST_EMAIL

        tree = ET.ElementTree(root)

    # Build new <item>
    now = datetime.now(timezone.utc)
    audio_url = f"{AUDIO_BASE_URL}/{audio_filename}" if AUDIO_BASE_URL else audio_filename
    file_size = _get_file_size_mb(audio_path)
    duration_secs = 300  # approximate 5 min; update if you have actual duration

    item = ET.Element("item")
    ET.SubElement(item, "title").text = episode_title
    ET.SubElement(item, "pubDate").text = _rfc822(now)
    ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = f"ep-{episode_number}-{now.strftime('%Y%m%d')}"
    ET.SubElement(item, "description").text = script_excerpt[:500] + "..."
    ET.SubElement(item, "itunes:episode").text = str(episode_number)
    ET.SubElement(item, "itunes:duration").text = str(duration_secs)
    ET.SubElement(item, "enclosure", {
        "url":    audio_url,
        "type":   "audio/mpeg",
        "length": str(file_size),
    })

    # Insert at top (most recent first)
    channel.insert(list(channel).index(channel.find("title")) + 6, item)

    ET.indent(root, space="  ")
    tree.write(RSS_FILE, encoding="unicode", xml_declaration=True)
    print(f"[rss] Feed updated → {RSS_FILE}  (episode #{episode_number})")


def get_next_episode_number() -> int:
    if not os.path.exists(RSS_FILE):
        return 1
    tree = ET.parse(RSS_FILE)
    items = tree.getroot().findall(".//item")
    return len(items) + 1
