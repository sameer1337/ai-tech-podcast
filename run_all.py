"""
Multi-podcast orchestrator — runs all 7 niches in sequence.
Called by GitHub Actions daily. Each podcast gets its own episode + RSS feed.

Usage:
  python run_all.py              # run all podcasts
  python run_all.py --id crypto  # run one specific podcast
  python run_all.py --test       # script only, no TTS
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

from niches import PODCASTS, PODCAST_MAP

TEST_MODE  = "--test" in sys.argv
SINGLE_ID  = next((sys.argv[sys.argv.index("--id") + 1] for i, a in enumerate(sys.argv) if a == "--id"), None)

TARGET_PODCASTS = [PODCAST_MAP[SINGLE_ID]] if SINGLE_ID else PODCASTS


def run_podcast(niche: dict) -> bool:
    """Run the full pipeline for one niche. Returns True on success."""
    from fetch_news   import fetch_stories_for_niche
    from generate_script import generate_script_for_niche
    from text_to_speech  import text_to_speech
    from publish_rss     import update_feed, get_next_episode_number

    pid   = niche["id"]
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    # Episode number tracked per-niche
    ep_num = get_next_episode_number(niche["rss_file"])
    audio_dir = niche["output_dir"]
    Path(audio_dir).mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  {niche['title']} — Episode #{ep_num} — {date_str}")
    print(f"{'='*60}")

    # Step 1: Fetch
    print(">> Step 1/4: Fetching stories...")
    stories = fetch_stories_for_niche(niche)
    if not stories:
        print(f"  [SKIP] No stories found for {pid}")
        return False

    # Step 2: Script
    print(">> Step 2/4: Generating script...")
    script = generate_script_for_niche(stories, niche)

    episode_title = f"{niche['title'].split()[0]} News {today.strftime('%b %d')} — {stories[0]['title'][:45]}"

    if TEST_MODE:
        print(f"\n[TEST] {episode_title}")
        print(script[:400] + "...\n")
        return True

    # Step 3: TTS
    print(">> Step 3/4: Synthesizing voice...")
    audio_filename = f"ep{ep_num:04d}_{date_str}.mp3"
    audio_path     = os.path.join(audio_dir, audio_filename)

    # Temporarily override voice in config
    import config as cfg
    original_voice = cfg.TTS_VOICE
    cfg.TTS_VOICE = niche.get("voice", cfg.TTS_VOICE)
    text_to_speech(script, audio_path)
    cfg.TTS_VOICE = original_voice

    # Step 4: RSS
    print(">> Step 4/4: Updating RSS feed...")
    # Build audio URL based on niche output dir
    base = cfg.PODCAST_WEBSITE_URL.rstrip("/")
    audio_url_path = f"{audio_dir}/{audio_filename}"
    update_feed(
        episode_title  = episode_title,
        audio_filename = audio_filename,
        audio_path     = audio_path,
        episode_number = ep_num,
        script_excerpt = script[:500],
        rss_file       = niche["rss_file"],
        audio_base_url = f"{base}/{audio_dir}",
        niche          = niche,
    )

    # Generate social media posts
    try:
        from generate_social import generate_social_posts
        social = generate_social_posts(niche, episode_title, script)
        log_dir = Path("logs") / pid
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / f"{date_str}_social.txt", "w", encoding="utf-8") as f:
            f.write(social["text"])
        print(f"  Social posts saved -> logs/{pid}/{date_str}_social.txt")
    except Exception as e:
        print(f"  [social] Warning: {e}")

    # Save log
    log_dir = Path("logs") / pid
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / f"{date_str}.json", "w") as f:
        json.dump({"date": date_str, "episode": ep_num, "title": episode_title,
                   "stories": [s["title"] for s in stories]}, f, indent=2)

    print(f"  Done: {audio_path}")
    return True


def main():
    from config import GROQ_API_KEY
    if GROQ_API_KEY == "YOUR_GROQ_KEY_HERE":
        print("ERROR: Set GROQ_API_KEY")
        sys.exit(1)

    results = {}
    for niche in TARGET_PODCASTS:
        try:
            ok = run_podcast(niche)
            results[niche["id"]] = "OK" if ok else "SKIPPED"
        except Exception as e:
            print(f"\n[ERROR] {niche['id']}: {e}")
            results[niche["id"]] = f"ERROR: {e}"

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for pid, status in results.items():
        icon = "OK" if status == "OK" else "!!"
        print(f"  [{icon}] {pid}: {status}")

    # Push to GitHub (skipped inside GitHub Actions — workflow handles it)
    if not os.environ.get("GITHUB_ACTIONS") and not TEST_MODE:
        import subprocess
        print("\nPushing to GitHub...")
        subprocess.run(["git", "add", "episodes/", "feeds/", "feed.xml", "logs/"], check=False)
        date_str = datetime.now().strftime("%Y-%m-%d")
        subprocess.run(["git", "commit", "-m", f"All episodes {date_str}"], check=False)
        subprocess.run(["git", "push"], check=False)


if __name__ == "__main__":
    main()
