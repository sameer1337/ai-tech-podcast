# -*- coding: utf-8 -*-
"""
Evening run — publish a NEW standalone long-form blog post per niche, text only
(NO podcast episode, audio, RSS, or video). This is what makes the site update
TWICE a day while the podcast + video stay once a day.

Stored as logs/web/<nid>/<YYYY-MM-DD>-<slug>.json and rendered by
generate_pages.build_web_posts + generate_home.

Usage:
  python run_blog.py                # all niches
  python run_blog.py --niche crypto
"""
import os, re, sys, json, time
from datetime import datetime, timezone
from email.utils import format_datetime
from niches import PODCASTS, PODCAST_MAP

ONE = next((sys.argv[sys.argv.index("--niche") + 1] for a in sys.argv if a == "--niche"), None)


def slugify(t, n=55):
    s = re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")
    return s[:n].rstrip("-") or "story"


def clean(t):
    t = re.sub(r"\s*[|\-–—:]\s*[A-Z][\w .]*$", "", (t or "").strip())
    return re.sub(r"\s{2,}", " ", t).strip(" -—|:·")[:70] or "Today's top story"


def run(niche):
    from fetch_news import fetch_stories_for_niche
    from generate_blog import generate_article
    nid = niche["id"]
    stories = fetch_stories_for_niche(niche)
    if not stories:
        print(f"[web] {nid}: no stories"); return False
    top = clean(stories[0]["title"])
    date = datetime.now().strftime("%Y-%m-%d")
    slug = f"{date}-{slugify(top)}"
    path = f"logs/web/{nid}/{slug}.json"
    if os.path.exists(path):
        print(f"[web] {nid}: already have {slug}, skipping"); return False
    art = generate_article(stories, niche)          # long-form + relevant image
    art["headline"] = top
    art["slug"] = slug
    art["date"] = date
    art["pubDate"] = format_datetime(datetime.now(timezone.utc))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(art, f, indent=2)
    print(f"[web] {nid}: saved {slug}")
    return True


def main():
    niches = [PODCAST_MAP[ONE]] if ONE else PODCASTS
    ok = 0
    for i, n in enumerate(niches):
        try:
            ok += 1 if run(n) else 0
        except Exception as e:
            print(f"[web] {n['id']} ERROR: {e}")
        if i < len(niches) - 1:
            time.sleep(5)
    print(f"\nWeb posts published: {ok}")


if __name__ == "__main__":
    main()
