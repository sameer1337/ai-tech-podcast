"""
Main orchestrator — runs the full pipeline end to end.
Scheduled via Windows Task Scheduler to run once daily.

Usage:
  python run_daily.py              # run full pipeline
  python run_daily.py --test       # generate script only, no TTS/RSS update
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR
from fetch_news import fetch_stories
from generate_script import generate_script
from text_to_speech import text_to_speech
from publish_rss import update_feed, get_next_episode_number

TEST_MODE = "--test" in sys.argv


def save_episode_log(episode_data: dict) -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{episode_data['date']}.json"
    with open(log_file, "w") as f:
        json.dump(episode_data, f, indent=2)
    print(f"[log] Episode log saved → {log_file}")


def main():
    from config import GROQ_API_KEY
    if GROQ_API_KEY == "YOUR_GROQ_KEY_HERE":
        print("ERROR: Set your GROQ_API_KEY in config.py or as an environment variable.")
        sys.exit(1)

    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    ep_num = get_next_episode_number()

    print(f"\n{'='*60}")
    print(f"  AI Tech Daily - Episode #{ep_num} - {date_str}")
    print(f"{'='*60}\n")

    # ── Step 1: Fetch news ───────────────────────────────────────
    print(">> Step 1/4: Fetching top stories...")
    stories = fetch_stories()
    if not stories:
        print("ERROR: No stories fetched. Check your internet connection.")
        sys.exit(1)

    # ── Step 2: Generate script ──────────────────────────────────
    print("\n>> Step 2/4: Generating podcast script with Claude...")
    script = generate_script(stories)

    episode_title = f"AI Tech Daily — {today.strftime('%B %d, %Y')}"

    if TEST_MODE:
        print("\n[TEST MODE] Script preview:\n")
        print(script[:1000] + "\n... (truncated)")
        print("\nTest complete. Run without --test to produce audio.")
        return

    # ── Step 3: Text to speech ───────────────────────────────────
    print("\n>> Step 3/4: Synthesizing voice with Edge TTS...")
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    audio_filename = f"ep{ep_num:04d}_{date_str}.mp3"
    audio_path = os.path.join(OUTPUT_DIR, audio_filename)
    text_to_speech(script, audio_path)

    # ── Step 4: Update RSS feed ──────────────────────────────────
    print("\n>> Step 4/4: Updating RSS feed...")
    update_feed(
        episode_title   = episode_title,
        audio_filename  = audio_filename,
        audio_path      = audio_path,
        episode_number  = ep_num,
        script_excerpt  = script[:500],
    )

    # ── Save log ─────────────────────────────────────────────────
    save_episode_log({
        "date":    date_str,
        "episode": ep_num,
        "title":   episode_title,
        "stories": [s["title"] for s in stories],
        "words":   len(script.split()),
        "audio":   audio_path,
    })

    print(f"\nDONE: Episode #{ep_num} complete!")
    print(f"  Audio : {audio_path}")
    print(f"  Feed  : feed.xml")

    # Auto-push to GitHub Pages so the episode goes live immediately
    import subprocess
    print("\nPushing to GitHub...")
    subprocess.run(["git", "add", audio_path, "feed.xml", f"logs/{date_str}.json"], check=True)
    subprocess.run(["git", "commit", "-m", f"Episode {ep_num} - {date_str}"], check=True)
    result = subprocess.run(["git", "push"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Live at: https://sameer1337.github.io/ai-tech-podcast/episodes/{audio_filename}")
    else:
        print(f"  Push failed: {result.stderr}")


if __name__ == "__main__":
    main()
