"""
auto_poster.py — multi-channel Social Auto-Poster + Distribution agent.

Reads today's issue (newsletter/today.json, written by run_newsletter.py) and
publishes it to every channel you've configured with credentials. Channels with
no credentials are skipped silently, so you can turn them on one at a time.

ToS-safe by design — it only posts to YOUR OWN pages/channels via official APIs:
  Telegram channel · Bluesky · Facebook Page · Instagram Business · Dev.to (backlink)
It deliberately does NOT touch X/Twitter personal, Reddit, or personal LinkedIn —
automating those gets accounts banned (those stay copy-paste from TODAY.md).

Credentials (set as env vars / GitHub Secrets; each channel is independent):
  Telegram : TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID   (e.g. @aitechdaily or -100…)
  Bluesky  : BLUESKY_HANDLE, BLUESKY_APP_PASSWORD
  Facebook : FB_PAGE_ID, FB_PAGE_TOKEN
  Instagram: IG_USER_ID, IG_TOKEN   (+ IG_IMAGE_URL or falls back to the cover)
  Dev.to   : DEVTO_API_KEY

Usage:
  python auto_poster.py            # post to every configured channel
  python auto_poster.py --dry      # build posts + show what WOULD go out, no network
  python auto_poster.py --only telegram,bluesky
"""

import os
import re
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

TODAY_JSON = Path("newsletter/today.json")
COVER_URL  = os.environ.get("IG_IMAGE_URL",
             "https://sameer1337.github.io/ai-tech-podcast/assets/cover.png")
BRAND = "AI Tech Daily"


# ── content ────────────────────────────────────────────────────────────────
def load_today():
    if not TODAY_JSON.exists():
        print(f"  [error] {TODAY_JSON} not found — run run_newsletter.py first.")
        return None
    return json.loads(TODAY_JSON.read_text(encoding="utf-8"))

def short_post(d, limit=280):
    """A punchy hook + link, sized for microblog channels."""
    hook = (d.get("tweet") or d.get("top_headline") or d.get("subject") or "").strip()
    url = d.get("archive_url") or d.get("sub_url") or ""
    # strip any URL the model may have baked into the tweet; we append our own
    hook = re.sub(r"https?://\S+", "", hook).strip()
    room = limit - len(url) - 2
    if len(hook) > room:
        hook = hook[:room - 1].rstrip() + "…"
    return (hook + "\n" + url).strip(), url

def devto_body(d):
    lines = [d.get("intro", ""), ""]
    for i, it in enumerate(d.get("items", []), 1):
        h = it.get("headline", ""); b = it.get("blurb", ""); u = it.get("url", "")
        src = it.get("source", "")
        lines.append(f"## {i}. {h}")
        lines.append(b)
        if u:
            lines.append(f"\n[Source{f' — {src}' if src else ''}]({u})")
        lines.append("")
    lines.append("---")
    lines.append(f"*This ran in **{BRAND}**, a free daily 5-minute AI brief you can also "
                 f"listen to. [Subscribe]({d.get('sub_url','https://daily.mapt.cloud')}).*")
    return "\n".join(lines)


# ── channels (each returns (ok:bool, msg:str)) ──────────────────────────────
def _cfg(*keys):
    vals = [os.environ.get(k, "").strip() for k in keys]
    return vals if all(vals) else None

def post_telegram(d, dry):
    c = _cfg("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID")
    if not c: return None
    token, chat = c
    text, _ = short_post(d, limit=900)
    body = f"<b>{BRAND}</b>\n\n{text}"
    if dry: return (True, "would send to " + chat)
    r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   json={"chat_id": chat, "text": body, "parse_mode": "HTML",
                         "disable_web_page_preview": False}, timeout=20)
    return (r.status_code == 200, f"HTTP {r.status_code}")

def post_bluesky(d, dry):
    c = _cfg("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD")
    if not c: return None
    handle, pw = c
    text, url = short_post(d, limit=290)
    if dry: return (True, "would post as " + handle)
    s = httpx.post("https://bsky.social/xrpc/com.atproto.server.createSession",
                   json={"identifier": handle, "password": pw}, timeout=20)
    if s.status_code != 200:
        return (False, f"auth HTTP {s.status_code}")
    sess = s.json()
    record = {"$type": "app.bsky.feed.post", "text": text,
              "createdAt": datetime.now(timezone.utc).isoformat()}
    # make the URL a clickable facet
    if url and url in text:
        b = text.encode("utf-8")
        start = b.find(url.encode("utf-8"))
        if start >= 0:
            record["facets"] = [{
                "index": {"byteStart": start, "byteEnd": start + len(url.encode("utf-8"))},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]}]
    r = httpx.post("https://bsky.social/xrpc/com.atproto.repo.createRecord",
                   headers={"Authorization": "Bearer " + sess["accessJwt"]},
                   json={"repo": sess["did"], "collection": "app.bsky.feed.post",
                         "record": record}, timeout=20)
    return (r.status_code == 200, f"HTTP {r.status_code}")

def post_facebook(d, dry):
    c = _cfg("FB_PAGE_ID", "FB_PAGE_TOKEN")
    if not c: return None
    page, token = c
    msg = (d.get("linkedin") or d.get("intro") or d.get("subject") or "").strip()
    link = d.get("archive_url") or d.get("sub_url")
    if dry: return (True, "would post to page " + page)
    r = httpx.post(f"https://graph.facebook.com/v21.0/{page}/feed",
                   data={"message": msg, "link": link, "access_token": token}, timeout=25)
    return (r.status_code == 200, f"HTTP {r.status_code}")

def post_instagram(d, dry):
    c = _cfg("IG_USER_ID", "IG_TOKEN")
    if not c: return None
    ig, token = c
    caption = ((d.get("linkedin") or d.get("intro") or "").strip()
               + "\n\nFull brief + audio → link in bio. "
               + (d.get("hashtags") or "#AI #tech #AInews"))
    if dry: return (True, "would post image to IG " + ig)
    # 1) create media container
    c1 = httpx.post(f"https://graph.facebook.com/v21.0/{ig}/media",
                    data={"image_url": COVER_URL, "caption": caption,
                          "access_token": token}, timeout=30)
    if c1.status_code != 200:
        return (False, f"container HTTP {c1.status_code}")
    cid = c1.json().get("id")
    # 2) publish
    c2 = httpx.post(f"https://graph.facebook.com/v21.0/{ig}/media_publish",
                    data={"creation_id": cid, "access_token": token}, timeout=30)
    return (c2.status_code == 200, f"HTTP {c2.status_code}")

def distribute_devto(d, dry):
    key = os.environ.get("DEVTO_API_KEY", "").strip()
    if not key: return None
    article = {"article": {
        "title": (d.get("top_headline") or d.get("subject") or BRAND)[:120],
        "body_markdown": devto_body(d),
        "published": True,
        "canonical_url": d.get("archive_url") or None,   # backlink to your site
        "tags": ["ai", "news", "technology", "newsletter"],
    }}
    if dry: return (True, "would publish to dev.to (canonical → your site)")
    r = httpx.post("https://dev.to/api/articles",
                   headers={"api-key": key, "Content-Type": "application/json"},
                   json=article, timeout=30)
    return (r.status_code in (200, 201), f"HTTP {r.status_code}")


CHANNELS = {
    "telegram":  post_telegram,
    "bluesky":   post_bluesky,
    "facebook":  post_facebook,
    "instagram": post_instagram,
    "devto":     distribute_devto,
}


def main():
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    args = sys.argv[1:]
    dry = "--dry" in args
    only = None
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))

    d = load_today()
    if not d:
        sys.exit(1)

    print(f"\n{'='*54}\n  Auto-poster — {d.get('date')}  {'(dry run)' if dry else ''}\n{'='*54}")
    if dry:
        txt, _ = short_post(d)
        print("  Microblog post preview:\n  " + txt.replace("\n", "\n  ") + "\n")

    any_configured = False
    for name, fn in CHANNELS.items():
        if only and name not in only:
            continue
        res = fn(d, dry)
        if res is None:
            print(f"  [skip] {name:10} — not configured")
            continue
        any_configured = True
        ok, msg = res
        print(f"  [{'ok ' if ok else 'FAIL'}] {name:10} — {msg}")

    if not any_configured:
        print("\n  No channels configured yet. Add credentials (see the header of this file)")
        print("  for any channel and it activates automatically on the next run.")
    print()


if __name__ == "__main__":
    main()
