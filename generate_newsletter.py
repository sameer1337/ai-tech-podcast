"""
Generate the AI Tech Daily EMAIL NEWSLETTER from the same daily AI stories the
podcast/blog already fetch. This is the text-email layer that monetizes via
beehiiv (sponsorships + premium + affiliates).

Pipeline position:
    fetch_news.py  →  (this file)  →  newsletter/<date>.html   (archive, deployed to blog)
                                   →  newsletter.xml            (RSS → beehiiv auto-send)

Nothing here sends email directly. beehiiv pulls newsletter.xml on a schedule
(RSS-to-send automation) OR run_newsletter.py pushes via the beehiiv API.
Keeping the send in beehiiv gives us deliverability + unsubscribe compliance
+ the growth/ad network for free.

Usage:
    python generate_newsletter.py --test    # print subject + text brief, write nothing
    python generate_newsletter.py           # write html + rss archive for today
"""

import os
import re
import sys
import json
import html
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from config import GROQ_API_KEY, GROQ_MODEL

# The newsletter uses a LIGHTER model than the podcasts on purpose: short email +
# social copy doesn't need the 70B, and llama-3.1-8b-instant draws from a
# SEPARATE (larger) free-tier daily token pool — so the newsletter never
# competes with the 7 podcasts for the 70B model's 100k/day budget.
NL_MODEL = os.environ.get("NEWSLETTER_GROQ_MODEL", "llama-3.1-8b-instant")

# ── Brand / links (edit once here) ────────────────────────────────────────
BRAND        = "AI Tech Daily"
TAGLINE      = "The 5-minute AI brief you can also listen to."
SITE_BASE    = "https://daily.mapt.cloud"
NEWS_BASE    = f"{SITE_BASE}/newsletter"           # where archive pages live
SPOTIFY_URL  = "https://open.spotify.com/show/033GtiveqJ3namuIWD009h"
SUBSCRIBE_URL= f"{SITE_BASE}/#subscribe"
# beehiiv gives each publication a referral/subscribe URL — paste it here once
# you create the publication (see NEWSLETTER_SETUP.md). Leaving it as SUBSCRIBE_URL
# is a safe default until then.
BEEHIIV_SUB_URL = os.environ.get("BEEHIIV_SUB_URL", SUBSCRIBE_URL)

NEWS_DIR = Path("newsletter")
RSS_PATH = Path("newsletter.xml")

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_TAGS  = re.compile(r"<[^>]+>")


def _plain(s: str) -> str:
    """Strip HTML/whitespace from a feed summary (HN/RSS embed markup)."""
    s = _TAGS.sub(" ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


# ── 1. Build the brief with Groq (free) ───────────────────────────────────
def build_brief(stories: list[dict]) -> dict:
    """Turn raw fetched stories into an email-ready brief.

    Returns: {subject, preview, intro, items:[{headline, blurb, source, url}]}
    Falls back to a template brief if Groq is unavailable so the pipeline
    never hard-fails on a bad API day.
    """
    stories = stories[:5]
    stories_block = "\n\n".join(
        f"Story {i}: {s['title']}\nSource: {s.get('source','')}\nURL: {s.get('link', s.get('url',''))}\n"
        f"Summary: {s.get('summary','')[:600]}"
        for i, s in enumerate(stories, 1)
    )

    prompt = f"""You write "{BRAND}", a punchy free daily email covering the biggest AI + tech news.
Tone: smart, fast, a little witty — like TLDR AI or The Rundown. Skimmable. No fluff.

From today's stories below, produce a JSON object with EXACTLY these keys:
  "subject": an irresistible email subject line, max 55 chars, no clickbait, front-loads the biggest story. No emoji spam (one emoji max, optional).
  "preview": inbox preview text, max 90 chars, complements the subject (don't repeat it).
  "intro": ONE warm, witty sentence to open the email (max 160 chars).
  "items": array of up to 5 objects, most important first, each:
      "headline": max 70 chars, keyword-first, no source name
      "blurb": 2 tight sentences — what happened + why it matters. Plain text, no markup.
      "source": the publication name
      "url": the story URL exactly as given
Do NOT invent facts, numbers, or quotes not in the summaries. Return ONLY the JSON.

Today's stories:
{stories_block}
"""

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=NL_MODEL,
            max_tokens=1400,
            temperature=0.6,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _FENCE.sub("", resp.choices[0].message.content.strip())
        data = json.loads(raw)
        items = []
        for it in (data.get("items") or [])[:5]:
            items.append({
                "headline": str(it.get("headline", "")).strip()[:80],
                "blurb":    str(it.get("blurb", "")).strip(),
                "source":   str(it.get("source", "")).strip()[:40],
                "url":      str(it.get("url", "")).strip(),
            })
        if not items:
            raise ValueError("no items returned")
        return {
            "subject": (data.get("subject") or f"{BRAND}: today's AI news").strip()[:60],
            "preview": (data.get("preview") or TAGLINE).strip()[:100],
            "intro":   (data.get("intro") or "Here's what matters in AI today.").strip()[:180],
            "items":   items,
        }
    except Exception as e:  # graceful fallback — never break the daily run
        print(f"  [warn] Groq brief failed ({e}); using template fallback.")
        items = [{
            "headline": _plain(s["title"])[:80],
            "blurb":    _plain(s.get("summary", ""))[:220],
            "source":   s.get("source", ""),
            "url":      s.get("link", s.get("url", "")),
        } for s in stories]
        return {
            "subject": f"{BRAND}: {stories[0]['title'][:45]}" if stories else f"{BRAND}: today in AI",
            "preview": TAGLINE,
            "intro":   "Here's what matters in AI today.",
            "items":   items,
        }


# ── 2. Render the email / archive HTML ────────────────────────────────────
def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def render_email_html(brief: dict, date_str: str, *, for_archive: bool = False) -> str:
    """Inline-CSS HTML that renders in email clients AND as a blog archive page.

    Contains ONE sponsor slot ({{SPONSOR}}) that beehiiv's ad network / your
    direct sponsor fills. If BEEHIIV handles ads, it injects its own; the
    placeholder simply shows house copy until a sponsor is booked.
    """
    try:
        pretty_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %d, %Y")
    except Exception:
        pretty_date = date_str

    stories_html = ""
    for i, it in enumerate(brief["items"], 1):
        src = f' <span style="color:#888">· {_esc(it["source"])}</span>' if it.get("source") else ""
        link_open  = f'<a href="{_esc(it["url"])}" style="color:#111;text-decoration:none" target="_blank">' if it.get("url") else ""
        link_close = "</a>" if it.get("url") else ""
        read_more  = (f'<a href="{_esc(it["url"])}" style="color:#2563eb;font-size:13px;'
                      f'text-decoration:none" target="_blank">Read more →</a>' if it.get("url") else "")
        stories_html += f"""
        <tr><td style="padding:18px 0;border-bottom:1px solid #eee">
          <div style="font-size:12px;color:#2563eb;font-weight:700;letter-spacing:.04em;text-transform:uppercase">
            {i:02d}{src}
          </div>
          <h2 style="margin:6px 0 6px;font-size:19px;line-height:1.3;color:#111">
            {link_open}{_esc(it["headline"])}{link_close}
          </h2>
          <p style="margin:0 0 8px;font-size:15px;line-height:1.6;color:#333">{_esc(it["blurb"])}</p>
          {read_more}
        </td></tr>"""

    sponsor_block = """
        <tr><td style="padding:16px;background:#f6f7f9;border-radius:10px;text-align:center">
          <div style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Together with</div>
          <div style="font-size:15px;color:#555">{{SPONSOR}} &nbsp;—&nbsp;
            <a href="mailto:hunk1.on11@gmail.com?subject=Sponsor%20AI%20Tech%20Daily" style="color:#2563eb;text-decoration:none">Book this slot →</a>
          </div>
        </td></tr>"""

    return f"""<!-- {BRAND} — {date_str} -->
<div style="margin:0;padding:0;background:#fff">
<div style="display:none;max-height:0;overflow:hidden">{_esc(brief.get('preview',''))}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fff">
<tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">

  <tr><td style="padding-bottom:6px">
    <div style="font-size:22px;font-weight:800;color:#111">{BRAND}</div>
    <div style="font-size:13px;color:#888">{TAGLINE} · {pretty_date}</div>
  </td></tr>

  <tr><td style="padding:10px 0 6px;font-size:16px;line-height:1.6;color:#222">
    {_esc(brief.get('intro',''))}
  </td></tr>

  {sponsor_block}

  <tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{stories_html}</table></td></tr>

  <tr><td style="padding:22px 0 6px">
    <a href="{SPOTIFY_URL}" target="_blank"
       style="display:inline-block;background:#1DB954;color:#fff;font-weight:700;font-size:15px;
              padding:12px 22px;border-radius:24px;text-decoration:none">
      🎧 Prefer to listen? Play today's 5-min episode
    </a>
  </td></tr>

  <tr><td style="padding:24px 0 8px;border-top:1px solid #eee;margin-top:16px">
    <p style="font-size:13px;color:#888;line-height:1.6;margin:8px 0">
      Enjoyed this? <a href="{BEEHIIV_SUB_URL}" style="color:#2563eb;text-decoration:none">Forward it to a friend</a>
      — or <a href="{BEEHIIV_SUB_URL}" style="color:#2563eb;text-decoration:none">subscribe here</a> if someone shared it with you.
    </p>
    <p style="font-size:12px;color:#aaa;margin:8px 0">
      {BRAND} · You're receiving this because you subscribed at daily.mapt.cloud.<br>
      {{{{unsubscribe}}}} · {{{{address}}}}
    </p>
  </td></tr>

</table></td></tr></table></div>"""


# ── 3. Maintain the RSS feed beehiiv reads ────────────────────────────────
def _rss_shell() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>\n'
        f'<title>{BRAND} — Daily Email</title>\n'
        f'<link>{NEWS_BASE}</link>\n'
        f'<description>{_esc(TAGLINE)}</description>\n'
        '<language>en-us</language>\n'
        '<!--ITEMS-->\n'
        '</channel></rss>\n'
    )


def append_to_rss(brief: dict, inner_html: str, date_str: str) -> None:
    """Prepend today's issue as an RSS <item>. beehiiv's RSS automation turns
    each new item into an email send. Keeps the newest ~60 items."""
    archive_url = f"{NEWS_BASE}/{date_str}.html"
    pub = format_datetime(datetime.now(timezone.utc))
    item = (
        "<item>\n"
        f"<title>{_esc(brief['subject'])}</title>\n"
        f"<link>{archive_url}</link>\n"
        f"<guid isPermaLink=\"true\">{archive_url}</guid>\n"
        f"<pubDate>{pub}</pubDate>\n"
        f"<description><![CDATA[{inner_html}]]></description>\n"
        "<content:encoded xmlns:content=\"http://purl.org/rss/1.0/modules/content/\">"
        f"<![CDATA[{inner_html}]]></content:encoded>\n"
        "</item>"
    )
    if RSS_PATH.exists():
        xml = RSS_PATH.read_text(encoding="utf-8")
    else:
        xml = _rss_shell()
    # Avoid double-posting the same date if run twice in one day.
    if f"{date_str}.html</link>" in xml:
        xml = re.sub(r"<item>.*?" + re.escape(f"{date_str}.html") + r".*?</item>\s*",
                     "", xml, count=1, flags=re.DOTALL)
    xml = xml.replace("<!--ITEMS-->", item + "\n<!--ITEMS-->", 1)
    # Trim to newest ~60 items
    items = re.findall(r"<item>.*?</item>", xml, flags=re.DOTALL)
    if len(items) > 60:
        for old in items[60:]:
            xml = xml.replace(old, "")
    RSS_PATH.write_text(xml, encoding="utf-8")


def write_archive_page(inner_html: str, brief: dict, date_str: str) -> Path:
    """Standalone archive page (also deployed to the blog for SEO + social share)."""
    NEWS_DIR.mkdir(exist_ok=True)
    page = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(brief['subject'])} — {BRAND}</title>
<meta name="description" content="{_esc(brief.get('preview',''))}">
<link rel="canonical" href="{NEWS_BASE}/{date_str}.html">
</head><body style="margin:0;background:#fff">{inner_html}</body></html>"""
    out = NEWS_DIR / f"{date_str}.html"
    out.write_text(page, encoding="utf-8")
    # keep a stable "latest" copy
    (NEWS_DIR / "latest.html").write_text(page, encoding="utf-8")
    return out


# ── 4. Public entry point ─────────────────────────────────────────────────
def generate(stories: list[dict], date_str: str | None = None, *, test: bool = False) -> dict:
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    brief = build_brief(stories)

    if test:
        print(f"\nSUBJECT : {brief['subject']}")
        print(f"PREVIEW : {brief['preview']}")
        print(f"INTRO   : {brief['intro']}\n")
        for i, it in enumerate(brief["items"], 1):
            print(f"{i:02d}. {it['headline']}  [{it['source']}]")
            print(f"    {it['blurb']}")
        print()
        return brief

    inner = render_email_html(brief, date_str)
    page = write_archive_page(inner, brief, date_str)
    append_to_rss(brief, inner, date_str)
    print(f"  [newsletter] archive → {page}")
    print(f"  [newsletter] rss     → {RSS_PATH}")
    brief["_archive_path"] = str(page)
    brief["_inner_html"] = inner
    return brief


def _load_today_stories() -> list[dict]:
    """Fetch today's AI stories using the existing pipeline."""
    try:
        from niches import PODCAST_MAP
        niche = PODCAST_MAP.get("ai-tech")
        if niche:
            from fetch_news import fetch_stories_for_niche
            return fetch_stories_for_niche(niche)
    except Exception as e:
        print(f"  [warn] niche fetch failed ({e}); falling back to fetch_stories().")
    from fetch_news import fetch_stories
    return fetch_stories()


if __name__ == "__main__":
    test = "--test" in sys.argv
    stories = _load_today_stories()
    if not stories:
        print("ERROR: no stories fetched.")
        sys.exit(1)
    generate(stories, test=test)
