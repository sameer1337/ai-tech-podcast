"""
Upload a generated Short (shorts/<niche>_<date>.mp4) to the Velox Daily channel.

Reuses the OAuth client + resumable uploader from upload_youtube.py (including
its exit-code-3 behaviour on quota/upload-limit errors).

Dedupe: logs/uploaded/short_<niche>_<date>.txt marker, same pattern as episodes.

Usage:
  python upload_short.py --niche startup [--date 2026-07-09]
"""

import os
import sys
import json
import argparse
from datetime import datetime

from niches import PODCAST_MAP
from upload_youtube import (get_youtube_client, upload_to_youtube, CATEGORY_IDS,
                            REFRESH_TOKEN, _load_used_titles, register_title)


def build_short_description(niche: dict, meta: dict) -> str:
    site = "https://daily.mapt.cloud"
    slug_map = {
        "ai-tech": "ai-tech", "finance": "finance", "health": "health",
        "startup": "startup", "crypto": "crypto",
        "world-news": "world", "true-crime": "truecrime",
    }
    nid = niche["id"]
    tag = nid.replace("-", "")
    return (
        f"{meta['story']}\n\n"
        f"This is the short version. The full story - with all of today's "
        f"{niche['title']} coverage - is free on every podcast app.\n\n"
        f"Full episode (Spotify): {niche.get('spotify_url', '')}\n"
        f"Written article: {site}/{slug_map.get(nid, nid)}\n"
        f"All daily briefings: {site}\n\n"
        f"#Shorts #{tag} #news #VeloxDaily #{niche['title'].replace(' ', '')}\n"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", required=True)
    parser.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    from generate_short import TOPICS
    niche = PODCAST_MAP.get(args.niche)
    if not niche and args.niche not in TOPICS:
        print(f"[error] Unknown niche/topic: {args.niche}")
        sys.exit(1)
    if not REFRESH_TOKEN:
        print("[skip] YT_REFRESH_TOKEN not set - skipping Short upload")
        sys.exit(0)

    marker = f"logs/uploaded/short_{args.niche}_{args.date}.txt"
    if os.path.exists(marker):
        print(f"[skip] Short already uploaded ({marker})")
        sys.exit(0)

    video_path = f"shorts/{args.niche}_{args.date}.mp4"
    meta_path = f"logs/{args.niche}/{args.date}_short.json"
    if not os.path.exists(video_path) or not os.path.exists(meta_path):
        print(f"[skip] No Short found for {args.niche} on {args.date}")
        sys.exit(0)

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    title = meta["title"][:88].strip()
    if title.strip().lower() in _load_used_titles() or \
       f"{title} #Shorts".strip().lower() in _load_used_titles():
        title = f"{title} ({datetime.utcnow().strftime('%b %d')})"
    if "#shorts" not in title.lower():
        title = f"{title} #Shorts"

    # Topic Shorts (e.g. worldcup) carry their own metadata in the json
    if meta.get("description"):
        desc = meta["description"]
        tags = meta.get("tags", ["Velox Daily", "shorts"])
        category = meta.get("category", "25")
    else:
        desc = build_short_description(niche, meta)
        tags = [niche["title"], "Velox Daily", "shorts", "news", args.niche][:30]
        category = CATEGORY_IDS.get(args.niche, "25")

    youtube = get_youtube_client()
    video_id = upload_to_youtube(youtube, video_path, title, desc, category, tags)

    register_title(title)
    os.makedirs("logs/uploaded", exist_ok=True)
    with open(marker, "w") as f:
        f.write(video_id)
    with open(f"logs/{args.niche}/{args.date}_short_youtube.txt", "w") as f:
        f.write(video_id)
    print(f"[done] Short live: https://youtube.com/shorts/{video_id}")


if __name__ == "__main__":
    main()
