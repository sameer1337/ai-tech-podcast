# ─────────────────────────────────────────────
#  AI Tech Daily Podcast — Configuration
# ─────────────────────────────────────────────

import os

# ── Groq API (free) ───────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_KEY_HERE")

# ── Podcast identity ───────────────────────────
PODCAST_TITLE       = "AI Tech Daily"
PODCAST_DESCRIPTION = "Your daily 5-minute briefing on the latest in AI and technology."
PODCAST_AUTHOR      = "AI Tech Daily"
PODCAST_EMAIL       = "hunk1.on11@gmail.com"
PODCAST_LANGUAGE    = "en"
PODCAST_CATEGORY    = "Technology"
PODCAST_IMAGE_URL   = ""   # set after uploading cover art
PODCAST_WEBSITE_URL = ""   # set after GitHub Pages deploy

# ── Edge-TTS voice ────────────────────────────
# Full list: run `edge-tts --list-voices`
# Great options: en-US-GuyNeural (male), en-US-JennyNeural (female),
#                en-AU-NatashaNeural, en-GB-RyanNeural
TTS_VOICE = "en-US-GuyNeural"
TTS_RATE  = "+5%"    # slightly faster than default
TTS_PITCH = "+0Hz"

# ── RSS sources ───────────────────────────────
RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://hnrss.org/frontpage",           # Hacker News
]
MAX_ITEMS_PER_FEED = 5   # fetch top N from each feed
TOP_STORIES        = 5   # final stories to cover in the episode

# ── Output paths ─────────────────────────────
OUTPUT_DIR   = "episodes"
RSS_FILE     = "feed.xml"
INTRO_MUSIC  = "assets/intro.mp3"   # optional; leave blank to skip
OUTRO_MUSIC  = "assets/outro.mp3"   # optional; leave blank to skip
MUSIC_FADE   = 3   # seconds to fade music in/out

# ── Script settings ───────────────────────────
EPISODE_TARGET_WORDS = 700   # ~5 min at 140 wpm
