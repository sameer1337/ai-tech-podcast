# -*- coding: utf-8 -*-
"""
Backfill existing posts:
  - For the latest N episodes per niche that have a saved transcript, regenerate
    a LONG-FORM article (from the script) + a relevant image.
  - For every other existing article JSON missing an image_url, resolve one.

Usage:
  python backfill_blog.py                 # long-form latest 2/niche + images for all
  python backfill_blog.py --limit 3
  python backfill_blog.py --images-only   # only add images, no LLM calls
  python backfill_blog.py --niche crypto
"""
import os, re, sys, json, time
from niches import PODCASTS

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
LIMIT = int(next((sys.argv[sys.argv.index("--limit")+1] for a in sys.argv if a == "--limit"), 2))
IMAGES_ONLY = "--images-only" in sys.argv
ONE = next((sys.argv[sys.argv.index("--niche")+1] for a in sys.argv if a == "--niche"), None)


def _date(ep):
    m = DATE_RE.search(ep.get("audio_url", "")) or DATE_RE.search(ep.get("guid", ""))
    return m.group(1) if m else None


def _load(p):
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return f.read()
    return ""


def main():
    from fetch_image import fetch_image
    if not IMAGES_ONLY:
        from generate_blog import expand_script_to_article
    from niches import PODCAST_MAP

    niches = [PODCAST_MAP[ONE]] if ONE else PODCASTS
    long_done = img_done = 0

    for niche in niches:
        nid = niche["id"]
        eps_path = f"logs/episodes_{nid}.json"
        if not os.path.exists(eps_path):
            continue
        eps = sorted(json.load(open(eps_path, encoding="utf-8")), key=lambda x: x["number"], reverse=True)

        for i, ep in enumerate(eps):
            d = _date(ep)
            if not d:
                continue
            art_path = f"logs/{nid}/{d}_article.json"
            script = _load(f"logs/{nid}/{d}_script.txt")

            # 1) Long-form regeneration for the latest LIMIT episodes with a transcript
            if not IMAGES_ONLY and i < LIMIT and script:
                try:
                    art = expand_script_to_article(script, niche, ep.get("title", ""))
                    os.makedirs(os.path.dirname(art_path), exist_ok=True)
                    json.dump(art, open(art_path, "w", encoding="utf-8"), indent=2)
                    long_done += 1
                    time.sleep(6)  # be gentle on Groq rate limits
                    continue
                except Exception as e:
                    print(f"[backfill] long-form failed {nid} {d}: {e}")
                    time.sleep(6)

            # 2) Ensure an image on any existing article JSON that lacks one
            if os.path.exists(art_path):
                art = json.load(open(art_path, encoding="utf-8"))
                if not art.get("image_url"):
                    q = art.get("image_query") or art.get("title") or ep.get("title", "")
                    art["image_url"] = fetch_image(q, abs(hash(q)) % 9973, 900, 520)
                    json.dump(art, open(art_path, "w", encoding="utf-8"), indent=2)
                    img_done += 1

    print(f"\nBackfill done: {long_done} long-form articles, {img_done} images added.")


if __name__ == "__main__":
    main()
