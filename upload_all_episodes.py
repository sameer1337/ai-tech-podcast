"""
One-time bulk upload of ALL existing episodes across all 7 niches.
Run after setting YT_REFRESH_TOKEN and YT_CHANNEL_ID env vars.

Usage:
  set YT_REFRESH_TOKEN=your_token
  set YT_CHANNEL_ID=UCxxxxxxx
  set GOOGLE_CLIENT_ID=xxx
  set GOOGLE_CLIENT_SECRET=xxx
  python upload_all_episodes.py

  # Upload only one niche:
  python upload_all_episodes.py --niche crypto

  # Dry run (no uploads):
  python upload_all_episodes.py --dry-run
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

from niches import PODCASTS, PODCAST_MAP

EPISODE_DIRS = {
    "ai-tech":    "episodes",
    "finance":    "episodes/finance",
    "health":     "episodes/health",
    "startup":    "episodes/startup",
    "crypto":     "episodes/crypto",
    "world-news": "episodes/world",
    "true-crime": "episodes/truecrime",
}


def get_episodes(niche_id: str) -> list:
    """Return list of (ep_num, date, mp3_path) sorted oldest first."""
    d = EPISODE_DIRS.get(niche_id, "episodes")
    if not os.path.isdir(d):
        return []
    eps = []
    for f in sorted(Path(d).glob("ep*.mp3")):
        name = f.stem  # ep0001_2026-06-29
        parts = name.split("_", 1)
        if len(parts) == 2:
            ep_num = int(parts[0][2:])
            date   = parts[1]
            eps.append((ep_num, date, str(f)))
    return eps


def load_stories(niche_id: str, date: str) -> list:
    path = f"logs/{niche_id}/{date}_stories.txt"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return [s.strip() for s in f.read().split("||") if s.strip()]
    jpath = f"logs/{niche_id}/{date}.json"
    if os.path.exists(jpath):
        try:
            with open(jpath, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("stories", [])[:4]
        except Exception:
            pass
    return []


def extract_stories_from_script(script: str) -> list:
    """Pull story headlines out of a script by finding sentence-starting lines."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    # Skip intro/outro lines, grab sentences that look like headlines
    headlines = []
    skip_phrases = ("welcome to", "that wraps", "stay curious", "see you tomorrow",
                    "subscribe", "today is", "here are the top")
    for s in sentences:
        s = s.strip()
        if len(s) < 30 or len(s) > 200:
            continue
        if any(s.lower().startswith(p) for p in skip_phrases):
            continue
        # Prefer sentences that start with a proper noun or key phrase
        if re.match(r'^[A-Z][a-z]', s):
            headlines.append(s)
        if len(headlines) >= 5:
            break
    return headlines


def load_script(niche_id: str, date: str) -> str:
    path = f"logs/{niche_id}/{date}_script.txt"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""



def mark_uploaded(niche_id: str, ep_num: int, date: str, video_id: str = ""):
    os.makedirs("logs/uploaded", exist_ok=True)
    with open(f"logs/uploaded/ep_{ep_num}_{date}_{niche_id}.txt", "w") as f:
        f.write(video_id)


def is_uploaded(niche_id: str, ep_num: int, date: str) -> bool:
    return (
        os.path.exists(f"logs/uploaded/ep_{ep_num}_{date}_{niche_id}.txt") or
        os.path.exists(f"logs/{niche_id}/{date}_youtube.txt")
    )


def upload_episode(niche_id: str, ep_num: int, date: str, mp3: str,
                   story_offset: int, dry_run: bool):
    stories = load_stories(niche_id, date)

    # If no stories file, try extracting from script
    if not stories:
        script_text = load_script(niche_id, date)
        if script_text:
            stories = extract_stories_from_script(script_text)

    # Rotate stories so each episode on the same day uses a different headline
    if stories and story_offset > 0:
        stories = stories[story_offset:] + stories[:story_offset]

    stories_arg = "||".join(stories[:4])
    script_file = f"logs/{niche_id}/{date}_script.txt"
    top = stories[0][:60] if stories else "no stories"
    print(f"\n  -> ep{ep_num:04d} ({date}) [{story_offset}] — {top}")

    if dry_run:
        print("  [DRY RUN] Would run upload_youtube.py")
        return True

    cmd = [
        sys.executable, "upload_youtube.py",
        "--niche",   niche_id,
        "--episode", mp3,
        "--number",  str(ep_num),
        "--stories", stories_arg,
    ]
    if os.path.exists(script_file):
        cmd += ["--script-file", script_file]

    result = subprocess.run(cmd, env=os.environ)
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche",   default="", help="Upload only this niche")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not os.environ.get("YT_REFRESH_TOKEN") and not args.dry_run:
        print("ERROR: Set YT_REFRESH_TOKEN environment variable first")
        sys.exit(1)

    niches = [PODCAST_MAP[args.niche]] if args.niche else PODCASTS
    total_ok = 0
    total_skip = 0
    total_fail = 0
    quota_hit = False

    for niche in niches:
        nid = niche["id"]
        eps = get_episodes(nid)
        print(f"\n{'='*55}")
        print(f"  {niche['title']} — {len(eps)} episodes found")
        print(f"{'='*55}")

        # Count episodes per date so we can rotate story offsets
        from collections import defaultdict, Counter
        date_counter: dict = defaultdict(int)

        for ep_num, date, mp3 in eps:
            if is_uploaded(nid, ep_num, date):
                print(f"  [skip] ep{ep_num:04d} ({date}) already uploaded")
                total_skip += 1
                continue

            # story_offset: 0 for first ep of the day, 1 for second, etc.
            story_offset = date_counter[date]
            date_counter[date] += 1

            rc = upload_episode(nid, ep_num, date, mp3, story_offset, args.dry_run)
            if rc is True or rc == 0:
                mark_uploaded(nid, ep_num, date)
                total_ok += 1
            elif rc == 3:
                print(f"  [QUOTA] YouTube daily upload quota exhausted — stopping run.")
                print(f"  Re-run after midnight Pacific Time; already-uploaded episodes will be skipped.")
                quota_hit = True
                break
            else:
                print(f"  [FAIL] ep{ep_num:04d} ({date})")
                total_fail += 1
        if quota_hit:
            break

    print(f"\n{'='*55}")
    print(f"  DONE — uploaded: {total_ok}  skipped: {total_skip}  failed: {total_fail}")
    if quota_hit:
        print(f"  STOPPED EARLY: daily quota exhausted — resume tomorrow")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
