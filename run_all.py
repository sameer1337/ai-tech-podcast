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


def _clean_headline(raw: str, limit: int = 60) -> str:
    """Trim a source headline for use in an episode title.

    Cuts on a word boundary (never mid-word) and strips trailing
    punctuation/quotes so titles don't end with stray characters like " AI'".
    """
    title = " ".join((raw or "").split())            # collapse whitespace
    # Drop a trailing source tag like " - TechCrunch" or " | Reuters"
    for sep in (" - ", " | ", " — "):
        if sep in title:
            title = title.split(sep)[0].strip()
            break
    if len(title) > limit:
        title = title[:limit].rsplit(" ", 1)[0]      # back off to last full word
    return title.rstrip(" \"'’‘“”-—–,.:;")


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
    ep_num = get_next_episode_number(niche["rss_file"], niche=niche)
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

    # Topic-first title: the searchable keyword leads, brand trails (podcast-app
    # search and Google weight the front of the title most heavily).
    top_story = _clean_headline(stories[0]['title']) if stories else "Top Stories"
    episode_title = f"{top_story} — {niche['title']} | {today.strftime('%b %d')}"

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

    # Generate the expanded blog article (website text layer + SEO)
    try:
        from generate_blog import generate_article
        article = generate_article(stories, niche)
        art_dir = Path("logs") / pid
        art_dir.mkdir(parents=True, exist_ok=True)
        with open(art_dir / f"{date_str}_article.json", "w", encoding="utf-8") as f:
            json.dump(article, f, indent=2)
        print(f"  Blog article saved -> logs/{pid}/{date_str}_article.json")
    except Exception as e:
        print(f"  [blog] Warning: {e}")

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
    story_titles = [s["title"] for s in stories]
    with open(log_dir / f"{date_str}.json", "w") as f:
        json.dump({"date": date_str, "episode": ep_num, "title": episode_title,
                   "stories": story_titles}, f, indent=2)
    # Write story headlines for YouTube video generation (|| separated)
    with open(log_dir / f"{date_str}_stories.txt", "w", encoding="utf-8") as f:
        f.write("||".join(story_titles[:4]))
    # Write full script for subtitle generation
    with open(log_dir / f"{date_str}_script.txt", "w", encoding="utf-8") as f:
        f.write(script)

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

    # Refresh Alexa Flash Briefing feeds from the updated episode DBs
    try:
        from generate_flash_briefing import build_all as build_flash
        build_flash()
    except Exception as e:
        print(f"[flash] Warning: {e}")

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
