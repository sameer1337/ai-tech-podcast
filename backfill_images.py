"""
One-time backfill: existing published articles have `image_url` pointing at a
remote hotlink (loremflickr/openverse) resolved before fetch_and_cache_image()
existed, so generate_pages.py just reuses that stored string forever, dead
links and all. This re-resolves + downloads a fresh local image for every
article JSON that isn't already using a local /assets/ path.

Safe to re-run: skips articles that already have a local image_url.
"""
import glob
import json
import os

from fetch_image import fetch_and_cache_image

NICHE_DIRS = [d for d in glob.glob("logs/*") if os.path.isdir(d) and os.path.basename(d) != "web"]
WEB_DIRS = [d for d in glob.glob("logs/web/*") if os.path.isdir(d)]


def _backfill_file(path, nid):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    url = data.get("image_url", "")
    if url.startswith("/assets/"):
        return False  # already local
    title = data.get("title") or data.get("headline") or nid
    query = data.get("image_query") or title
    seed = abs(hash(title)) % 9973
    new_url = fetch_and_cache_image(query, f"blog/{nid}", str(seed), seed, 900, 520)
    if not new_url.startswith("/assets/"):
        # Remote source is dead/unreliable even on retry — clear it so the page falls back
        # to the local cached category image instead of a hotlink that may 500.
        new_url = ""
    if new_url == url:
        return False
    data["image_url"] = new_url
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def main():
    total = fixed = 0
    for d in NICHE_DIRS:
        nid = os.path.basename(d)
        for path in glob.glob(os.path.join(d, "*_article.json")):
            total += 1
            ok = _backfill_file(path, nid)
            print(f"[{'ok' if ok else '--'}] {path}")
            fixed += ok
    for d in WEB_DIRS:
        nid = os.path.basename(d)
        for path in glob.glob(os.path.join(d, "*.json")):
            total += 1
            ok = _backfill_file(path, nid)
            print(f"[{'ok' if ok else '--'}] {path}")
            fixed += ok
    print(f"\nBackfilled {fixed}/{total} article images to local assets/.")


if __name__ == "__main__":
    main()
