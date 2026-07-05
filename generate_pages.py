"""
Generate the full Mapt Daily blog site from episode data + generated articles.

Structure produced:
  index.html                       -> Mapt Daily home (latest posts, all niches)
  blog/<id>/index.html             -> category page (one niche, all posts)
  blog/<id>/<slug>.html            -> post: article + audio player + transcript
  about.html, privacy.html         -> required for AdSense / trust
  sitemap.xml, robots.txt          -> indexing
  CNAME                            -> custom domain
  podcasts/<id>/index.html         -> 301-style redirect to /blog/<id>/ (legacy)

Each post derives its article (logs/<id>/<date>_article.json) and transcript
(logs/<id>/<date>_script.txt) from files written by the daily run, matched to
the episode by the date embedded in its audio filename.
"""

import os
import re
import json
import html
from datetime import datetime, timezone
from niches import PODCASTS

SITE_URL = "https://daily.mapt.cloud"
BRAND    = "Mapt Daily"
AUDIO_BASE_FALLBACK = "https://sameer1337.github.io/ai-tech-podcast"

COLORS = {
    "ai-tech":    "#7c3aed", "finance": "#16a34a", "health": "#0891b2",
    "startup":    "#9333ea", "crypto":  "#d97706", "world-news": "#2563eb",
    "true-crime": "#dc2626",
}
ICONS = {
    "ai-tech": "🤖", "finance": "💰", "health": "🧬", "startup": "🚀",
    "crypto": "₿", "world-news": "🌍", "true-crime": "🔍",
}
CATEGORY_LABEL = {
    "ai-tech": "AI & Tech", "finance": "Finance", "health": "Health",
    "startup": "Startups", "crypto": "Crypto", "world-news": "World",
    "true-crime": "True Crime",
}

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


# ─────────────────────────── data loading ───────────────────────────
def load_episodes(nid):
    path = f"logs/episodes_{nid}.json"
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return sorted(json.load(f), key=lambda x: x["number"], reverse=True)


def _episode_date(ep):
    m = DATE_RE.search(ep.get("audio_url", "")) or DATE_RE.search(ep.get("guid", ""))
    return m.group(1) if m else None


def _load_article(nid, date):
    if not date:
        return None
    p = f"logs/{nid}/{date}_article.json"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def _load_transcript(nid, date):
    if not date:
        return ""
    p = f"logs/{nid}/{date}_script.txt"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    return ""


def slugify(text, maxlen=60):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:maxlen].rstrip("-")) or "episode"


def _topic_from_ep(title, niche):
    """Extract the specific story headline from an episode title, stripping the
    brand and date chrome. Works for both title formats (brand-first and
    topic-first). This is stable per episode, so it makes a durable URL slug."""
    t = (title or "").replace(niche["title"], " ")
    t = re.sub(r"\|\s*[A-Z][a-z]{2}\s*\d{1,2}", " ", t)   # drop "| Jul 05"
    t = re.sub(r"\s{2,}", " ", t).strip(" -—|·")
    return t or niche["title"]


def build_posts(niche):
    """Return a list of post dicts for a niche, newest first."""
    nid = niche["id"]
    posts = []
    for ep in load_episodes(nid):
        date = _episode_date(ep)
        article = _load_article(nid, date)
        transcript = _load_transcript(nid, date)
        # Headline/slug come from the episode's specific story (stable URL);
        # the article supplies dek, body, meta and tags.
        headline = _topic_from_ep(ep["title"], niche)
        slug = f"ep{ep['number']}-{slugify(headline)}"
        posts.append({
            "niche": niche,
            "number": ep["number"],
            "date": date or ep.get("pubDate", "")[:16],
            "pubDate": ep.get("pubDate", ""),
            "audio_url": ep.get("audio_url", ""),
            "duration": ep.get("duration", 300),
            "headline": headline,
            "dek": (article or {}).get("dek") or ep.get("description", "")[:150],
            "meta": (article or {}).get("meta_description") or niche["description"][:155],
            "body_html": (article or {}).get("body_html", ""),
            "tags": (article or {}).get("tags", []),
            "transcript": transcript,
            "excerpt": ((article or {}).get("dek") or ep.get("description", "")[:180]),
            "url": f"{SITE_URL}/blog/{nid}/{slug}.html",
            "path": f"blog/{nid}/{slug}.html",
        })
    return posts


# ─────────────────────────── shared chrome ───────────────────────────
CSS = """
*{margin:0;padding:0;box-sizing:border-box}
:root{--ink:#14161a;--soft:#5b6470;--line:#e6e8ec;--bg:#ffffff;--wash:#f7f8fa;--accent:#7c3aed}
body{font-family:Georgia,'Times New Roman',serif;color:var(--ink);background:var(--bg);line-height:1.7}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:760px;margin:0 auto;padding:0 22px}
.wide{max-width:1100px}
header.site{border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(255,255,255,.94);backdrop-filter:blur(6px);z-index:10}
.site-inner{max-width:1100px;margin:0 auto;padding:14px 22px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.brand{font-family:-apple-system,'Segoe UI',sans-serif;font-weight:800;font-size:1.25rem;color:var(--ink);letter-spacing:-.5px}
.brand span{color:var(--accent)}
.catnav{display:flex;gap:14px;flex-wrap:wrap;font-family:-apple-system,'Segoe UI',sans-serif;font-size:.82rem;font-weight:600}
.catnav a{color:var(--soft)}
.catnav a:hover{color:var(--ink);text-decoration:none}
.hero{padding:54px 0 30px;text-align:center;border-bottom:1px solid var(--line)}
.hero h1{font-family:-apple-system,'Segoe UI',sans-serif;font-size:2.4rem;font-weight:900;letter-spacing:-1px;margin-bottom:12px}
.hero p{color:var(--soft);font-size:1.05rem;max-width:560px;margin:0 auto}
.eyebrow{font-family:-apple-system,'Segoe UI',sans-serif;text-transform:uppercase;letter-spacing:.12em;font-size:.72rem;font-weight:700;color:var(--accent)}
.feed{padding:34px 0}
.post-card{padding:24px 0;border-bottom:1px solid var(--line)}
.post-card .eyebrow{color:var(--soft)}
.post-card .tag{color:var(--accent)}
.post-card h2{font-size:1.5rem;line-height:1.25;margin:6px 0 8px;font-weight:800}
.post-card h2 a{color:var(--ink)}
.post-card p{color:var(--soft);font-size:1rem}
.meta{font-family:-apple-system,'Segoe UI',sans-serif;font-size:.78rem;color:var(--soft);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
article.post{padding:36px 0 10px}
article.post h1{font-family:-apple-system,'Segoe UI',sans-serif;font-size:2.15rem;line-height:1.2;font-weight:900;letter-spacing:-.6px;margin:10px 0 12px}
article.post .dek{font-size:1.2rem;color:var(--soft);margin-bottom:20px;font-style:italic}
.player{background:var(--wash);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:22px 0}
.player .plabel{font-family:-apple-system,'Segoe UI',sans-serif;font-size:.8rem;font-weight:700;color:var(--ink);margin-bottom:10px}
audio{width:100%;height:40px}
.body h2{font-family:-apple-system,'Segoe UI',sans-serif;font-size:1.4rem;font-weight:800;margin:30px 0 10px}
.body p{margin:0 0 16px;font-size:1.12rem}
.body ul{margin:0 0 16px 22px}.body li{margin-bottom:8px;font-size:1.1rem}
.tags{margin:26px 0;font-family:-apple-system,'Segoe UI',sans-serif;font-size:.8rem}
.tags a{display:inline-block;background:var(--wash);border:1px solid var(--line);color:var(--soft);padding:4px 12px;border-radius:30px;margin:0 6px 8px 0}
details.transcript{border-top:1px solid var(--line);margin-top:30px;padding-top:8px}
details.transcript summary{font-family:-apple-system,'Segoe UI',sans-serif;font-weight:700;cursor:pointer;padding:12px 0;font-size:.95rem}
details.transcript p{color:#333;font-size:1.02rem;margin:0 0 14px}
.subscribe{background:var(--wash);border:1px solid var(--line);border-radius:12px;padding:20px;margin:34px 0;font-family:-apple-system,'Segoe UI',sans-serif}
.subscribe h3{font-size:1rem;margin-bottom:12px}
.subscribe a{display:inline-block;border:1px solid var(--line);background:#fff;border-radius:30px;padding:8px 16px;margin:0 8px 8px 0;font-size:.85rem;font-weight:600}
.breadcrumb{font-family:-apple-system,'Segoe UI',sans-serif;font-size:.78rem;color:var(--soft);padding:20px 0 0}
.cat-hero{padding:44px 0 20px;border-bottom:1px solid var(--line)}
.cat-hero .icon{font-size:2.4rem}
.cat-hero h1{font-family:-apple-system,'Segoe UI',sans-serif;font-size:2rem;font-weight:900;margin:6px 0}
footer.site{border-top:1px solid var(--line);margin-top:40px;padding:30px 0;font-family:-apple-system,'Segoe UI',sans-serif;font-size:.82rem;color:var(--soft)}
footer.site .wrap{max-width:1100px}
footer.site a{color:var(--soft)}
.disc{font-size:.78rem;color:#8a929c;margin-top:8px}
@media(max-width:600px){.hero h1{font-size:1.8rem}article.post h1{font-size:1.6rem}.catnav{font-size:.76rem;gap:10px}}
"""


def _catnav():
    links = " ".join(
        f'<a href="{SITE_URL}/blog/{n["id"]}/">{ICONS[n["id"]]} {CATEGORY_LABEL[n["id"]]}</a>'
        for n in PODCASTS
    )
    return f'<nav class="catnav">{links}</nav>'


def _head(title, desc, canonical, accent="#7c3aed", extra=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{BRAND}">
<meta name="twitter:card" content="summary_large_image">
<style>{CSS}:root{{--accent:{accent}}}</style>
{extra}
</head>
<body>
<header class="site"><div class="site-inner">
<a class="brand" href="{SITE_URL}/">Mapt<span>Daily</span></a>
{_catnav()}
</div></header>"""


def _footer():
    return f"""<footer class="site"><div class="wrap">
<p><a href="{SITE_URL}/">Home</a> · <a href="{SITE_URL}/about.html">About</a> · <a href="{SITE_URL}/privacy.html">Privacy</a></p>
<p class="disc">© {datetime.now().year} {BRAND}. Daily news across AI, finance, health, startups, crypto, world &amp; true crime. Audio and article summaries are AI-assisted and compiled from public news sources; verify before relying on any detail.</p>
</div></footer>
</body></html>"""


# ─────────────────────────── page builders ───────────────────────────
def post_page(post):
    n = post["niche"]; nid = n["id"]; accent = COLORS[nid]
    audio = post["audio_url"] or ""
    body = post["body_html"] or f"<p>{html.escape(post['dek'])}</p>"

    transcript_html = ""
    if post["transcript"]:
        paras = "".join(f"<p>{html.escape(p.strip())}</p>"
                        for p in re.split(r"\n\s*\n", post["transcript"]) if p.strip())
        transcript_html = f"""<details class="transcript"><summary>📄 Full episode transcript</summary>{paras}</details>"""

    tags_html = ""
    if post["tags"]:
        tags_html = '<div class="tags">' + "".join(
            f'<a href="{SITE_URL}/blog/{nid}/">#{html.escape(t)}</a>' for t in post["tags"]
        ) + "</div>"

    subscribe = f"""<div class="subscribe"><h3>🎧 Listen to {html.escape(n['title'])} daily</h3>
<a href="{SITE_URL}/{n['rss_file']}">📡 RSS</a>
<a href="{SITE_URL}/blog/{nid}/">More {CATEGORY_LABEL[nid]} stories</a></div>"""

    ld = {
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": post["headline"][:110],
        "description": post["meta"],
        "datePublished": _iso(post["pubDate"]),
        "dateModified": _iso(post["pubDate"]),
        "author": {"@type": "Organization", "name": n["title"]},
        "publisher": {"@type": "Organization", "name": BRAND},
        "mainEntityOfPage": post["url"],
        "articleSection": CATEGORY_LABEL[nid],
    }
    schema = f'<script type="application/ld+json">{json.dumps(ld)}</script>'

    player = ""
    if audio:
        player = f"""<div class="player"><div class="plabel">▶ Listen · 5 min</div>
<audio controls preload="none" src="{html.escape(audio)}"></audio></div>"""

    return _head(f"{post['headline']} — {BRAND}", post["meta"], post["url"], accent, schema) + f"""
<div class="wrap">
<div class="breadcrumb"><a href="{SITE_URL}/">Home</a> › <a href="{SITE_URL}/blog/{nid}/">{CATEGORY_LABEL[nid]}</a></div>
<article class="post">
<div class="eyebrow" style="color:{accent}">{ICONS[nid]} {CATEGORY_LABEL[nid]}</div>
<h1>{html.escape(post['headline'])}</h1>
<div class="dek">{html.escape(post['dek'])}</div>
<div class="meta"><span>{post['date']}</span><span>·</span><span>{n['title']}</span></div>
{player}
<div class="body">{body}</div>
{tags_html}
{subscribe}
{transcript_html}
</article>
</div>
{_footer()}"""


def category_page(niche, posts):
    nid = niche["id"]; accent = COLORS[nid]
    cards = ""
    for p in posts:
        cards += f"""<div class="post-card">
<div class="meta"><span>{p['date']}</span></div>
<h2><a href="{p['url']}">{html.escape(p['headline'])}</a></h2>
<p>{html.escape(p['excerpt'])}</p>
</div>"""
    if not cards:
        cards = "<p style='padding:30px 0;color:#888'>New stories coming soon.</p>"

    canonical = f"{SITE_URL}/blog/{nid}/"
    return _head(f"{niche['title']} — {CATEGORY_LABEL[nid]} News | {BRAND}",
                 niche["description"][:155], canonical, accent) + f"""
<div class="cat-hero"><div class="wrap">
<div class="icon">{ICONS[nid]}</div>
<h1>{html.escape(niche['title'])}</h1>
<p style="color:var(--soft)">{html.escape(niche['description'])}</p>
<div class="subscribe" style="margin-top:18px"><h3>Subscribe</h3>
<a href="{SITE_URL}/{niche['rss_file']}">📡 RSS Feed</a></div>
</div></div>
<div class="wrap feed">{cards}</div>
{_footer()}"""


def home_page(all_posts):
    latest = sorted(all_posts, key=lambda p: p["pubDate"], reverse=True)[:24]
    cards = ""
    for p in latest:
        nid = p["niche"]["id"]
        cards += f"""<div class="post-card">
<div class="eyebrow tag" style="color:{COLORS[nid]}">{ICONS[nid]} {CATEGORY_LABEL[nid]}</div>
<h2><a href="{p['url']}">{html.escape(p['headline'])}</a></h2>
<p>{html.escape(p['excerpt'])}</p>
<div class="meta"><span>{p['date']}</span></div>
</div>"""

    return _head(f"{BRAND} — Daily News on AI, Finance, Health, Crypto, Startups & More",
                 "Mapt Daily: concise daily news and analysis across AI, finance, health, startups, crypto, world affairs and true crime. Read the article, hear the 5-minute brief.",
                 f"{SITE_URL}/") + f"""
<div class="hero"><div class="wrap">
<div class="eyebrow">Updated every morning</div>
<h1>Mapt Daily</h1>
<p>Concise daily news and analysis across seven beats. Read the story, then hear the five-minute brief.</p>
</div></div>
<div class="wrap feed">{cards}</div>
{_footer()}"""


def static_page(title, canonical, body_html):
    return _head(f"{title} — {BRAND}", f"{title} — {BRAND}", canonical) + f"""
<div class="wrap"><article class="post"><h1>{title}</h1><div class="body">{body_html}</div></article></div>
{_footer()}"""


def redirect_page(target):
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="{target}"><title>Moved</title></head>
<body><p>This page has moved to <a href="{target}">{target}</a>.</p></body></html>"""


# ─────────────────────────── helpers + sitemap ───────────────────────────
def _iso(pubdate):
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(pubdate).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sitemap(urls):
    body = "".join(
        f"\n  <url><loc>{u}</loc><changefreq>daily</changefreq></url>" for u in urls
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}\n</urlset>'


# ─────────────────────────── main ───────────────────────────
def _write(path, content):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    all_posts = []
    urls = [f"{SITE_URL}/", f"{SITE_URL}/about.html", f"{SITE_URL}/privacy.html"]

    for niche in PODCASTS:
        nid = niche["id"]
        posts = build_posts(niche)
        all_posts.extend(posts)

        # Clear stale post HTML so a changed slug never leaves an orphan/duplicate
        blog_dir = f"blog/{nid}"
        if os.path.isdir(blog_dir):
            for old in os.listdir(blog_dir):
                if old.endswith(".html"):
                    os.remove(os.path.join(blog_dir, old))

        _write(f"blog/{nid}/index.html", category_page(niche, posts))
        urls.append(f"{SITE_URL}/blog/{nid}/")

        for p in posts:
            _write(p["path"], post_page(p))
            urls.append(p["url"])

        # legacy podcast page -> redirect to new category
        _write(f"podcasts/{nid}/index.html", redirect_page(f"{SITE_URL}/blog/{nid}/"))
        print(f"[page] blog/{nid}/ ({len(posts)} posts)")

    _write("index.html", home_page(all_posts))

    about = ("<p><strong>Mapt Daily</strong> publishes concise daily news and analysis across seven beats: "
             "AI &amp; technology, finance, health, startups, crypto, world affairs and true crime. Each story is "
             "paired with a five-minute audio brief you can listen to anywhere.</p>"
             "<p>Our summaries are compiled from reputable public news sources and produced with AI assistance, "
             "then published every morning. We aim for accuracy and neutrality; if you spot an error, contact us at "
             "hunk1.on11@gmail.com.</p>")
    privacy = ("<p>This site is operated by Mapt Daily. We do not collect personal information directly. "
               "Standard server logs and third-party services (such as analytics and, where present, advertising "
               "partners like Google) may set cookies and collect usage data in accordance with their own policies.</p>"
               "<p>Third-party vendors, including Google, use cookies to serve ads based on prior visits to this or "
               "other websites. You can opt out of personalized advertising via Google Ads Settings. For questions "
               "about this policy, contact hunk1.on11@gmail.com.</p>")
    _write("about.html", static_page("About Mapt Daily", f"{SITE_URL}/about.html", about))
    _write("privacy.html", static_page("Privacy Policy", f"{SITE_URL}/privacy.html", privacy))

    _write("sitemap.xml", sitemap(urls))
    _write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    # NOTE: CNAME is intentionally NOT written here. Set the custom domain via
    # GitHub repo Settings > Pages (which creates CNAME) only AFTER the DNS
    # record for daily.mapt.cloud exists, or the live site will break.

    print(f"[page] home + about + privacy + sitemap ({len(urls)} urls) + robots")


if __name__ == "__main__":
    main()
