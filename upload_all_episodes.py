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
    # Fall back to JSON log
    jpath = f"logs/{niche_id}/{date}.json"
    if os.path.exists(jpath):
        with open(jpath, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("stories", [])[:4]
    return []


def load_script(niche_id: str, date: str) -> str:
    path = f"logs/{niche_id}/{date}_script.txt"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""


def already_uploaded(niche_id: str, date: str) -> bool:
    return os.path.exists(f"logs/{niche_id}/{date}_youtube.txt")


def upload_episode(niche_id: str, ep_num: int, date: str, mp3: str, dry_run: bool):
    stories = load_stories(niche_id, date)
    script  = load_script(niche_id, date)
    stories_arg = "||".join(stories[:4])
    script_file = f"logs/{niche_id}/{date}_script.txt"

    print(f"\n  -> Uploading ep{ep_num:04d} ({date}) — {stories[0][:60] if stories else 'no stories'}")

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
    return result.returncode == 0


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

    for niche in niches:
        nid = niche["id"]
        eps = get_episodes(nid)
        print(f"\n{'='*55}")
        print(f"  {niche['title']} — {len(eps)} episodes found")
        print(f"{'='*55}")

        for ep_num, date, mp3 in eps:
            if already_uploaded(nid, date):
                print(f"  [skip] ep{ep_num:04d} ({date}) already uploaded")
                total_skip += 1
                continue

            ok = upload_episode(nid, ep_num, date, mp3, args.dry_run)
            if ok:
                total_ok += 1
            else:
                print(f"  [FAIL] ep{ep_num:04d} ({date})")
                total_fail += 1

    print(f"\n{'='*55}")
    print(f"  DONE — uploaded: {total_ok}  skipped: {total_skip}  failed: {total_fail}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
