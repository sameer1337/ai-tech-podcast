"""
Post the ready Shorts batch to YouTube, with thumbnails.

Reads shorts_metadata.json, uploads each video via the resumable uploader in
ai-tech-podcast/upload_youtube.py, then sets the matching custom thumbnail.
Already-uploaded videos are skipped via markers in uploaded/.

Credentials (env vars — same ones the GitHub Actions pipeline uses):
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    YT_REFRESH_TOKEN            # Velox Daily channel
    YT_REFRESH_TOKEN_AMERICA    # America Unveiled channel (optional)

Usage:
    python post_shorts.py --channel velox-daily --dry-run
    python post_shorts.py --channel velox-daily
    python post_shorts.py --channel velox-daily --only football_01
    python post_shorts.py --channel velox-daily --privacy private
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
# upload_youtube.py lives in the podcast repo. Locally that's a sibling folder;
# in CI this script sits inside that repo, so its parent is the repo root.
for cand in (os.path.join(os.path.dirname(ROOT), "ai-tech-podcast"),
             os.path.dirname(ROOT)):
    if os.path.exists(os.path.join(cand, "upload_youtube.py")):
        sys.path.insert(0, cand)
        break

META = os.path.join(ROOT, "shorts_metadata.json")
MARKERS = os.environ.get("MARKER_DIR") or os.path.join(ROOT, "uploaded")

# Where the mp4s/jpgs live. Locally that's this folder; in CI it's the flat
# directory the release assets were downloaded into.
MEDIA_DIR = os.environ.get("MEDIA_DIR") or ROOT


def resolve(item, key):
    """Find a media file whether it's laid out in series subfolders (local) or
    flattened with a series prefix (release assets)."""
    rel = item[key].replace("/", os.sep)
    base = os.path.basename(rel)
    for cand in (os.path.join(MEDIA_DIR, rel),
                 os.path.join(MEDIA_DIR, f"{item['series']}_{base}"),
                 os.path.join(MEDIA_DIR, base)):
        if os.path.exists(cand):
            return cand
    return os.path.join(MEDIA_DIR, rel)   # non-existent; caller reports it

TOKEN_ENV = {
    "velox-daily":     "YT_REFRESH_TOKEN",
    "america-unveiled": "YT_REFRESH_TOKEN_AMERICA",
}


def load(channel, only=None):
    with open(META, encoding="utf-8") as f:
        items = json.load(f)
    items = [i for i in items if i["channel"] == channel]
    if only:
        wanted = set(only)
        items = [i for i in items if i["id"] in wanted]
        missing = wanted - {i["id"] for i in items}
        if missing:
            sys.exit(f"[error] unknown id(s): {', '.join(sorted(missing))}")
    return items


def set_thumbnail(youtube, video_id, path):
    from googleapiclient.http import MediaFileUpload
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(path, mimetype="image/jpeg"),
    ).execute()
    print(f"[thumbnail] set {os.path.basename(path)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="velox-daily", choices=sorted(TOKEN_ENV))
    ap.add_argument("--only", nargs="*", help="Upload only these metadata ids")
    ap.add_argument("--privacy", default="public",
                    choices=["public", "private", "unlisted"])
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate files, metadata and credentials without uploading")
    args = ap.parse_args()

    items = load(args.channel, args.only)
    if not items:
        sys.exit(f"[error] nothing to upload for channel {args.channel}")

    # Validate every file and thumbnail up front — never half-post a batch.
    problems = []
    for it in items:
        for key in ("file", "thumbnail"):
            p = resolve(it, key)
            if not os.path.exists(p):
                problems.append(f"missing {key}: {it[key]}")
            elif key == "thumbnail" and os.path.getsize(p) > 2 * 1024 * 1024:
                problems.append(f"thumbnail over YouTube's 2MB limit: {it[key]}")
        if len(it["title"]) > 100:
            problems.append(f"title over 100 chars: {it['id']}")
    if problems:
        print("[error] pre-flight failed:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print(f"[ok] pre-flight passed for {len(items)} video(s) on {args.channel}")

    env = TOKEN_ENV[args.channel]
    token = os.environ.get(env, "")
    if not token:
        print(f"\n[blocked] {env} is not set — cannot upload.")
        print("Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and "
              f"{env}, then re-run.")
        if not args.dry_run:
            sys.exit(2)

    if args.dry_run:
        print("\n[dry-run] would upload, in order:")
        for it in items:
            mb = os.path.getsize(resolve(it, "file")) // (1024 * 1024)
            print(f"  {it['id']:12s} {mb:3d}MB  {it['title']}")
        return

    import upload_youtube
    from upload_youtube import get_youtube_client, upload_to_youtube
    upload_youtube.REFRESH_TOKEN = token

    youtube = get_youtube_client(token)
    print(f"[auth] authenticated for {args.channel}")

    os.makedirs(MARKERS, exist_ok=True)
    posted = []
    for it in items:
        marker = os.path.join(MARKERS, f"{args.channel}_{it['id']}.txt")
        if os.path.exists(marker):
            print(f"[skip] {it['id']} already uploaded ({open(marker).read().strip()})")
            continue

        video = resolve(it, "file")
        thumb = resolve(it, "thumbnail")

        body_privacy = args.privacy
        vid = upload_to_youtube(
            youtube, video, it["title"], it["description"],
            category_id=it["category_id"], tags=it["tags"],
        )
        if body_privacy != "public":
            youtube.videos().update(
                part="status",
                body={"id": vid, "status": {"privacyStatus": body_privacy,
                                            "selfDeclaredMadeForKids": False}},
            ).execute()
            print(f"[privacy] set to {body_privacy}")

        try:
            set_thumbnail(youtube, vid, thumb)
        except Exception as e:
            print(f"[warn] thumbnail failed for {it['id']}: {e}")

        url = f"https://youtu.be/{vid}"
        with open(marker, "w") as f:
            f.write(url)
        posted.append((it["id"], url))

    print("\n=== posted ===")
    for pid, url in posted:
        print(f"  {pid:12s} {url}")
    if not posted:
        print("  (nothing new)")


if __name__ == "__main__":
    main()
