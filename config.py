# ─────────────────────────────────────────────
#  AI Tech Daily Podcast — Configuration
# ─────────────────────────────────────────────

import os

# ── Groq API (free) ───────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_KEY_HERE")
# One place to swap when Groq deprecates a model (see 2026-07 Scout email)
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── Podcast identity ───────────────────────────
PODCAST_TITLE       = "AI Tech Daily"
PODCAST_DESCRIPTION = "AI Tech Daily is your free daily AI news podcast — 5 minutes of the biggest artificial intelligence and tech news every morning. Stay ahead of AI, machine learning, ChatGPT, OpenAI, Google, and the tech industry. New episode every day, completely free."
PODCAST_AUTHOR      = "AI Tech Daily"
PODCAST_EMAIL       = "hunk1.on11@gmail.com"
PODCAST_LANGUAGE    = "en"
PODCAST_CATEGORY    = "Technology"
PODCAST_IMAGE_URL   = "https://sameer1337.github.io/ai-tech-podcast/assets/cover.png"
PODCAST_WEBSITE_URL = "https://sameer1337.github.io/ai-tech-podcast"

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
