# AI Tech Daily — Automated Faceless Podcast

Daily 5-minute AI & tech news podcast. Fully automated, no human involvement after setup.

## Pipeline

```
RSS Feeds → Claude Script → Edge TTS → MP3 → RSS Feed → All Platforms
```

## Quick Start

### 1. Install dependencies
```
pip install -r requirements.txt
```
Also install [ffmpeg](https://ffmpeg.org/download.html) and add it to PATH (needed by pydub).

### 2. Set your Anthropic API key
In `config.py`:
```python
ANTHROPIC_API_KEY = "sk-ant-..."
```
Or set as environment variable: `$env:ANTHROPIC_API_KEY = "sk-ant-..."`

### 3. Test run (no audio, just sees the script)
```
python run_daily.py --test
```

### 4. Full run (generates MP3 + updates feed.xml)
```
python run_daily.py
```

### 5. Set up daily automation
Run once as Administrator:
```
.\setup_scheduler.ps1
```
This registers a Windows Task Scheduler job that runs at 6 AM daily.

---

## Hosting the RSS Feed (Free)

1. Create a GitHub repo (e.g. `ai-tech-podcast`)
2. Enable GitHub Pages on the `main` branch
3. Set `PODCAST_WEBSITE_URL` in config.py to your Pages URL
4. After each run, `git add . && git commit -m "ep" && git push`
   (or automate this by adding git push to `run_daily.py`)

## Submit to Platforms (one-time setup)

Once you have 1 episode live, submit your RSS feed URL to:

| Platform | Submit URL |
|---|---|
| Spotify | podcasters.spotify.com |
| Apple Podcasts | podcastsconnect.apple.com |
| Amazon Music | music.amazon.com/podcasts/submit |
| Google Podcasts (via RSS) | Auto-indexed via Google Search |
| iHeartRadio | iheart.com/content/submit-your-podcast |
| Pocket Casts | pocketcasts.com/submit |

All platforms poll your RSS feed — new episodes appear automatically within hours.

## Optional: Add Intro/Outro Music

1. Get royalty-free music from [pixabay.com/music](https://pixabay.com/music/) (free)
2. Place files at `assets/intro.mp3` and `assets/outro.mp3`
3. Install pydub and ffmpeg — the pipeline mixes them automatically

## Folder Structure

```
ai-tech-podcast/
├── config.py              ← All settings here
├── run_daily.py           ← Main orchestrator
├── fetch_news.py          ← RSS news fetcher
├── generate_script.py     ← Claude script writer
├── text_to_speech.py      ← Edge TTS voice synthesis
├── publish_rss.py         ← RSS feed manager
├── setup_scheduler.ps1    ← Windows Task Scheduler setup
├── requirements.txt
├── episodes/              ← Generated MP3s (push to GitHub)
├── feed.xml               ← RSS feed (push to GitHub)
├── logs/                  ← Episode logs
└── assets/                ← Optional intro/outro music
```
