"""
Generate the Mapt Daily magazine website (Jannah-style) for daily.mapt.cloud.
Audio + RSS + covers stay on GitHub Pages (FEED_BASE); only the site is on Hostinger.
"""

import os
import re
import json
import html
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from niches import PODCASTS
from site_header import header_html, HEADER_CSS, HEADER_JS, analytics_head

SITE_URL  = "https://daily.mapt.cloud"
FEED_BASE = "https://sameer1337.github.io/ai-tech-podcast"
BRAND     = "Mapt Daily"
MAPT_URL  = "https://mapt.cloud"
VITA_URL  = "https://mapt.cloud/vita"

COLORS = {"ai-tech":"#7c3aed","finance":"#16a34a","health":"#0891b2","startup":"#e11d48",
          "crypto":"#d97706","world-news":"#ea580c","true-crime":"#111827"}
LABEL  = {"ai-tech":"AI & Tech","finance":"Finance","health":"Health","startup":"Startups",
          "crypto":"Crypto","world-news":"Trending","true-crime":"True Crime"}
IMG_KW = {"ai-tech":"technology,ai,computer","finance":"finance,money,business",
          "health":"health,medical,fitness","startup":"startup,office,teamwork",
          "crypto":"cryptocurrency,bitcoin,blockchain","world-news":"crowd,viral,city,news",
          "true-crime":"police,night,investigation"}
# Editable: your real social handles + display counts (placeholders shown to match layout)
SOCIALS = [("Facebook","f-fb","#","1.2K","Fans"),("X","f-x","#","480","Followers"),
           ("YouTube","f-yt","#","2.1K","Subscribers"),("Instagram","f-ig","#","760","Followers"),
           ("LinkedIn","f-in","#","540","Followers"),("TikTok","f-tt","#","1.4K","Followers")]
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def img(nid, seed=0, w=800, h=500):
    """Cached local category fallback image (downloaded once, reused across sizes/renders)."""
    from fetch_image import fetch_and_cache_image
    return fetch_and_cache_image(IMG_KW.get(nid, "news"), "categories", nid, seed, w, h)


def pimg(p, w=800, h=500):
    """Prefer the article's resolved relevant image; fall back to keyworded generic."""
    return p.get("image_url") or img(p["nid"], p["seed"], w, h)


# ─────────── data ───────────
def load_episodes(nid):
    p = f"logs/episodes_{nid}.json"
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return sorted(json.load(f), key=lambda x: x["number"], reverse=True)


def _date(ep):
    m = DATE_RE.search(ep.get("audio_url","")) or DATE_RE.search(ep.get("guid",""))
    return m.group(1) if m else None


def _load_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _load_txt(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return ""


def slugify(t, n=60):
    s = re.sub(r"[^a-z0-9]+","-",(t or "").lower()).strip("-")
    return s[:n].rstrip("-") or "episode"


def _topic(title, niche):
    t = (title or "").replace(niche["title"]," ")
    t = re.sub(r"\|\s*[A-Z][a-z]{2}\s*\d{1,2}"," ",t)
    return re.sub(r"\s{2,}"," ",t).strip(" -—|·") or niche["title"]


def build_posts(niche):
    nid = niche["id"]; out = []
    for ep in load_episodes(nid):
        d = _date(ep)
        art = _load_json(f"logs/{nid}/{d}_article.json") if d else None
        vid = _load_txt(f"logs/{nid}/{d}_youtube.txt") if d else ""   # optional YT id
        head = (art or {}).get("title") or _topic(ep["title"], niche)
        slug = f"ep{ep['number']}-{slugify(head)}"
        out.append({
            "niche":niche,"nid":nid,"number":ep["number"],"seed":ep["number"]*7+hash(nid)%13,
            "date":d or ep.get("pubDate","")[:16],"pubDate":ep.get("pubDate",""),
            "audio_url":ep.get("audio_url",""),"video_id":vid,
            "headline":head,
            "dek":(art or {}).get("dek") or ep.get("description","")[:150],
            "meta":(art or {}).get("meta_description") or niche["description"][:155],
            "body_html":(art or {}).get("body_html",""),"tags":(art or {}).get("tags",[]),
            "image_url":(art or {}).get("image_url") or "",
            "transcript":_load_txt(f"logs/{nid}/{d}_script.txt") if d else "",
            "excerpt":(art or {}).get("dek") or ep.get("description","")[:150],
            "url":f"{SITE_URL}/blog/{nid}/{slug}.html","href":f"/blog/{nid}/{slug}.html",
            "path":f"blog/{nid}/{slug}.html",
        })
    return out


def build_web_posts(niche):
    """Standalone text-only articles (evening run) not tied to a podcast episode.
    Stored as logs/web/<nid>/<slug>.json. Same post shape as episode posts."""
    nid = niche["id"]; d = f"logs/web/{nid}"; out = []
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        a = _load_json(os.path.join(d, fn)) or {}
        slug = a.get("slug") or fn[:-5]
        pslug = f"web-{slug}"
        out.append({
            "niche": niche, "nid": nid, "number": 0, "seed": abs(hash(slug)) % 9973,
            "date": a.get("date", ""), "pubDate": a.get("pubDate", ""),
            "audio_url": "", "video_id": "",
            "headline": a.get("headline") or a.get("title") or niche["title"],
            "dek": a.get("dek", ""), "meta": a.get("meta_description") or a.get("dek", ""),
            "body_html": a.get("body_html", ""), "tags": a.get("tags", []),
            "image_url": a.get("image_url", ""), "transcript": "", "excerpt": a.get("dek", ""),
            "url": f"{SITE_URL}/blog/{nid}/{pslug}.html", "href": f"/blog/{nid}/{pslug}.html",
            "path": f"blog/{nid}/{pslug}.html",
        })
    return out


def _iso(pd):
    try:
        return parsedate_to_datetime(pd).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return "1970-01-01T00:00:00Z"


# ─────────── shared chrome ───────────
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" '
         'href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?'
         'family=Inter:wght@400;500;600&family=Poppins:wght@500;600;700&display=swap" rel="stylesheet">')


def _header(all_posts, active="home"):
    """Shared mega-menu header (same on every page). all_posts = list of post dicts."""
    ca = {}
    for n in PODCASTS:
        nid = n["id"]
        ps = sorted([p for p in all_posts if p["nid"] == nid], key=lambda x: x["pubDate"], reverse=True)[:4]
        ca[nid] = [{"title": p["headline"], "href": p["href"],
                    "img": pimg(p, 400, 240), "date": p["date"]} for p in ps]
    breaking = [p["headline"] for p in sorted(all_posts, key=lambda x: x["pubDate"], reverse=True)[:5]] \
        or ["Mapt Daily — fresh news every day"]
    return header_html(ca, active=active, breaking=breaking)


def _footer(posts):
    recent = sorted(posts, key=lambda p:p["pubDate"], reverse=True)[:4]
    def fmini(p):
        return (f'<a class="fmini" href="{p["href"]}"><span class="th"><img loading="lazy" src="{pimg(p,120,90)}" alt=""></span>'
                f'<span><h5>{html.escape(p["headline"][:52])}</h5><span class="date">{p["date"]}</span></span></a>')
    mv = "".join(fmini(p) for p in recent)
    rc = "".join(fmini(p) for p in recent[::-1])
    tags = set()
    for p in posts:
        for t in p["tags"]:
            tags.add(t)
    tagcloud = "".join(f'<a href="#">{html.escape(t)}</a>' for t in list(tags)[:16]) or \
        "".join(f'<a href="/blog/{n["id"]}/">{LABEL[n["id"]]}</a>' for n in PODCASTS)
    fsoc = "".join(f'<a href="#">{p} · {n} {l}</a>' for p,_c,_u,n,l in SOCIALS)
    return f"""<footer class="foot">
<div class="foot-top">
<div><h4>Most Viewed</h4>{mv}</div>
<div><h4>Recent Posts</h4>{rc}</div>
<div><h4>Tags</h4><div class="ftags">{tagcloud}</div></div>
<div><h4>Follow Us</h4><div class="fsoc">{fsoc}</div></div>
</div>
<div class="foot-brand"><div class="in"><a class="logo" href="/">Mapt<b>Daily</b> <span>news</span></a>
<a class="btn-mini" style="background:var(--primary);color:#fff;padding:11px 22px" href="/mapt.html">Work with Mapt →</a></div></div>
<div class="foot-copy"><div class="in"><span>© {datetime.now().year} {BRAND} — a project of
<a href="{MAPT_URL}" style="margin:0">Mapt</a>. AI-assisted summaries from public news sources.</span>
<span><a href="/about.html">About</a><a href="/privacy.html">Privacy</a><a href="/mapt.html">Mapt</a><a href="/vita.html">Vita</a></span></div></div>
</footer><script defer src="/static/site.js"></script>{HEADER_JS}</body></html>"""


def _head(title, desc, canonical, extra="", accent="#2b6cff"):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}"><link rel="canonical" href="{canonical}">
<meta property="og:type" content="website"><meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}"><meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{BRAND}"><meta name="twitter:card" content="summary_large_image">
{FONTS}<link rel="stylesheet" href="/static/site.css"><style>:root{{--accent:{accent}}}</style>{HEADER_CSS}{analytics_head()}{extra}</head><body>"""


# ─────────── component builders ───────────
def _tag(p): return f'<span class="tag" style="background:{COLORS[p["nid"]]}">{LABEL[p["nid"]]}</span>'


def tile(p, cls, w, h, exc=False):
    e = f'<p class="exc">{html.escape(p["excerpt"])}</p>' if exc else ""
    return (f'<a class="tile {cls}" href="{p["href"]}"><img loading="lazy" src="{pimg(p,w,h)}" alt="">'
            f'<div class="cap">{_tag(p)}<h3>{html.escape(p["headline"])}</h3>{e}</div></a>')


def ncard(p):
    return (f'<a class="ncard" href="{p["href"]}"><div class="thumb"><img loading="lazy" src="{pimg(p,500,320)}" alt="">{_tag(p)}</div>'
            f'<div class="body"><h3 class="card-title">{html.escape(p["headline"])}</h3>'
            f'<span class="date">🕔 {p["date"]}</span></div></a>')


def titem(p, rank=None):
    r = f'<span class="rank">{rank}</span>' if rank else ""
    return (f'<a class="titem" href="{p["href"]}"><span class="th">{r}<img loading="lazy" src="{pimg(p,200,150)}" alt=""></span>'
            f'<span><h4 class="card-title">{html.escape(p["headline"])}</h4><span class="date">🕔 {p["date"]}</span></span></a>')


def thero(p, dark=False):
    return (f'<a class="thero" href="{p["href"]}"><img loading="lazy" src="{pimg(p,700,460)}" alt="">'
            f'<div class="cap">{_tag(p)}<h3 class="card-title">{html.escape(p["headline"])}</h3></div></a>')


def vcard(p):
    return (f'<a class="vcard" href="{p["href"]}"><img loading="lazy" src="{pimg(p,400,240)}" alt="">'
            f'<span class="play">▶</span><span class="t">{html.escape(p["headline"][:60])}</span></a>')


def hcard(p, hidden=False):
    return (f'<a class="hcard{" more" if hidden else ""}"{" hidden" if hidden else ""} href="{p["href"]}">'
            f'<span class="th"><img loading="lazy" src="{pimg(p,300,210)}" alt=""></span>'
            f'<span>{_tag(p)}<h3 class="card-title" style="margin-top:8px">{html.escape(p["headline"])}</h3>'
            f'<span class="date" style="display:block;margin-top:6px">🕔 {p["date"]} · {p["niche"]["title"]}</span></span></a>')


def promoband(kind):
    if kind == "mapt":
        return ('<a class="promoband mapt" href="/mapt.html"><div><h3>🚀 Built by Mapt</h3>'
                '<p>Websites, branding, marketing & AI automation — fast, all over text.</p></div>'
                '<span class="btn">Explore Mapt →</span></a>')
    return ('<a class="promoband vita" href="/vita.html"><div><h3>🧘 Meet Vita</h3>'
            '<p>Your AI wellness companion — habits, mood & insights. Free to start.</p></div>'
            '<span class="btn">Discover Vita →</span></a>')


def sidebar(posts, counts):
    recent = sorted(posts, key=lambda p:p["pubDate"], reverse=True)[:5]
    follow = "".join(f'<a class="fbtn {c}" href="#"><span><span class="n">{n}</span><br><span class="l">{l}</span></span></a>'
                     for p,c,_u,n,l in SOCIALS)
    rec = "".join(titem(p) for p in recent)
    pop = "".join(titem(p, i+1) for i,p in enumerate(recent[::-1]))
    cats = "".join(f'<a href="/blog/{n["id"]}/"><span class="ci"><img loading="lazy" src="{img(n["id"],n["id"].__hash__()%50+3,120,90)}" alt=""></span>'
                   f'<span class="cn">{LABEL[n["id"]]}</span><span class="cc">{counts.get(n["id"],0)}</span></a>' for n in PODCASTS)
    return f"""<aside class="side">
<div class="widget"><div class="wh">Follow <span>Us</span></div><div class="follow">{follow}</div></div>
<div class="widget weather"><div class="top"><div><div class="city">Weather</div><div class="date" style="color:#ffffffcc">Partly cloudy</div></div><div class="temp">24°</div></div>
<div class="fc"><span>☀<br>Mon</span><span>⛅<br>Tue</span><span>🌦<br>Wed</span><span>☀<br>Thu</span><span>⛅<br>Fri</span></div></div>
<div class="widget"><div class="wtabs"><button class="on" data-wt="rec">Recent</button><button data-wt="pop">Popular</button></div>
<div data-wp="rec"><div class="tlist">{rec}</div></div><div data-wp="pop" hidden><div class="tlist">{pop}</div></div></div>
<div class="widget newsletter"><div class="wh" style="color:#fff">Subscribe</div>
<p>Get the day's top stories in your inbox.</p>
<form class="mh-subform" data-source="sidebar"><input type="email" placeholder="Your email" required><button class="sub">Subscribe</button></form></div>
<div class="widget"><div class="wh">Categories</div><div class="catlist">{cats}</div></div>
<div class="adbox">Advertisement</div>
</aside>"""


# ─────────── pages ───────────
def home_page(all_posts, per_niche, counts):
    latest = sorted(all_posts, key=lambda p:p["pubDate"], reverse=True)
    L = (latest + latest)[:20]  # pad so indexing is safe with few posts
    breaking = [p["headline"] for p in latest[:6]] or ["Welcome to Mapt Daily"]

    # hero mosaic
    mosaic = f"""<section class="section"><div class="mosaic">
{tile(L[0],'lead',800,760,exc=True)}
<div class="msub">{tile(L[1],'big',700,450)}
<div class="row2">{tile(L[2],'sm',420,300)}{tile(L[3],'sm',420,300)}</div></div>
</div></section>"""

    # trending main column
    trend_tabs = "".join(f'<button data-tab="{n["id"]}">{LABEL[n["id"]]}</button>' for n in PODCASTS)
    trend_list = "".join(titem(p) for p in latest[5:10])
    trending = f"""<section class="section"><div class="block-head"><h2>Trending News</h2>
<div class="tabs"><button class="on" data-tab="all">All</button>{trend_tabs}</div></div>
<div class="trend">{thero(latest[4] if len(latest)>4 else L[4])}<div class="tlist">{trend_list}</div></div></section>"""

    def dark_section(nid):
        ps = per_niche.get(nid, [])[:5]
        if not ps: return ""
        lst = "".join(titem(p) for p in ps[1:5])
        return f"""<section class="section"><div class="darksec"><div class="block-head"><h2>{LABEL[nid]}</h2></div>
<div class="trend">{thero(ps[0], dark=True)}<div class="tlist">{lst}</div></div></div></section>"""

    def duo(nid_a, nid_b):
        def col(nid):
            ps = per_niche.get(nid, [])[:3]
            if not ps: return "<div></div>"
            mini = "".join(titem(p) for p in ps[1:3])
            return (f'<div><div class="block-head"><h2>{LABEL[nid]}</h2></div>{ncard(ps[0])}'
                    f'<div class="tlist" style="margin-top:14px">{mini}</div></div>')
        return f'<section class="section"><div class="duo">{col(nid_a)}{col(nid_b)}</div></section>'

    def wide():
        a,b = L[6], L[7]
        return (f'<section class="section"><div class="wideband">{tile(a,"big",700,420)}{tile(b,"big",700,420)}</div></section>')

    def videos():
        vids = latest[:4]
        if not vids: return ""
        grid = "".join(vcard(p) for p in vids[1:4])
        vh = vids[0]
        return f"""<section class="section videos-sec"><div class="darksec"><div class="block-head"><h2>Videos</h2></div>
<a class="vhero" href="{vh['href']}"><img loading="lazy" src="{pimg(vh,800,460)}" alt="">
<span class="play">▶</span><div class="cap">{_tag(vh)}<h3 class="card-title">{html.escape(vh['headline'])}</h3></div></a>
<div class="vgrid">{grid}</div></div></section>"""

    whats = latest[:8]
    wgrid = "".join(hcard(p, hidden=(i>=4)) for i,p in enumerate(whats))
    whatsnew = f"""<section class="section"><div class="block-head"><h2>What's New</h2></div>
<div class="grid2">{wgrid}</div><button class="loadmore" data-loadmore>Load More</button></section>"""

    main = (trending + promoband("mapt") + dark_section("startup") +
            duo("finance","health") + wide() + dark_section("ai-tech") +
            promoband("vita") + videos() + whatsnew)

    body = (mosaic + '<div class="container"><div class="layout"><div class="maincol">' +
            main + '</div>' + sidebar(all_posts, counts) + '</div></div>')

    return (_head(f"{BRAND} — Daily News on AI, Finance, Health, Crypto, Startups & More",
                  "Mapt Daily: daily news and analysis across AI, finance, health, startups, crypto, world "
                  "and true crime — read the story, hear the five-minute brief.", f"{SITE_URL}/")
            + _header(all_posts) + body + _footer(all_posts))


def category_page(niche, posts, all_posts, counts):
    nid = niche["id"]
    grid = "".join(ncard(p) for p in posts) or '<p>New stories coming soon.</p>'
    body = f"""<div class="container"><div class="cathero" style="background:{COLORS[nid]}">
<h1>{html.escape(niche['title'])}</h1><p>{html.escape(niche['description'])}</p></div>
<div class="layout"><div class="maincol"><section class="section"><div class="grid2">{grid}</div></section></div>
{sidebar(all_posts, counts)}</div></div>"""
    return (_head(f"{niche['title']} — {LABEL[nid]} News | {BRAND}", niche["description"][:155],
                  f"{SITE_URL}/blog/{nid}/", accent=COLORS[nid])
            + _header(all_posts, active=nid)
            + body + _footer(all_posts))


def post_page(p, all_posts, counts):
    nid = p["nid"]; niche = p["niche"]
    body = p["body_html"] or f"<p>{html.escape(p['dek'])}</p>"
    lead = (f'<div class="video-embed"><iframe loading="lazy" src="https://www.youtube.com/embed/{p["video_id"]}" '
            f'title="video" allowfullscreen></iframe></div>') if p["video_id"] else \
           f'<div class="lead-img"><img src="{pimg(p,900,520)}" alt="{html.escape(p["headline"])}"></div>'
    player = (f'<div class="player"><div class="pl">▶ Listen · 5 min</div>'
              f'<audio controls preload="none" src="{html.escape(p["audio_url"])}"></audio></div>') if p["audio_url"] else ""
    tx = ""
    if p["transcript"]:
        paras = "".join(f"<p>{html.escape(x.strip())}</p>" for x in re.split(r"\n\s*\n",p["transcript"]) if x.strip())
        tx = f'<details class="transcript"><summary>📄 Full episode transcript</summary><div class="tx">{paras}</div></details>'
    tags = ('<div class="tagrow">' + "".join(f'<a href="/blog/{nid}/">#{html.escape(t)}</a>' for t in p["tags"]) + "</div>") if p["tags"] else ""
    ld = {"@context":"https://schema.org","@type":"NewsArticle","headline":p["headline"][:110],
          "description":p["meta"],"datePublished":_iso(p["pubDate"]),"dateModified":_iso(p["pubDate"]),
          "image":[pimg(p,900,520)],"author":{"@type":"Organization","name":niche["title"]},
          "publisher":{"@type":"Organization","name":BRAND},"mainEntityOfPage":p["url"],"articleSection":LABEL[nid]}
    schema = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    art = f"""<div class="container"><div class="layout"><div class="maincol"><article class="post">
<div class="breadcrumb"><a href="/">Home</a> › <a href="/blog/{nid}/">{LABEL[nid]}</a></div>
{_tag(p)}<h1>{html.escape(p['headline'])}</h1><p class="dek">{html.escape(p['dek'])}</p>
<div class="meta"><span>🕔 {p['date']}</span><span>·</span><span>{niche['title']}</span></div>
{lead}{player}<div class="body">{body}</div>{tags}
<div class="promoband mapt" style="margin-top:26px"><div><h3>🚀 Built by Mapt</h3>
<p>Like this site? Mapt builds websites, brands & growth engines — over text.</p></div>
<a class="btn" href="/mapt.html">Explore →</a></div>{tx}</article></div>
{sidebar(all_posts, counts)}</div></div>"""
    return (_head(f"{p['headline']} — {BRAND}", p["meta"], p["url"], schema, COLORS[nid])
            + _header(all_posts, active=nid)
            + art + _footer(all_posts))


def landing(kind, all_posts):
    if kind == "mapt":
        feats = [("🌐","Websites & Apps","Fast, modern, responsive sites — like this one."),
                 ("🎨","Brand & Design","Logos and identity that look established from day one."),
                 ("📈","Growth & Marketing","SEO, content engines and funnels that bring customers in."),
                 ("🤖","AI Automation","Custom AI workflows that handle the busywork."),
                 ("💬","Text-First, No Calls","Everything over text. No meetings, just momentum."),
                 ("🌏","AU / NZ & Global","Built for Australia & New Zealand, delivered worldwide.")]
        fh = "".join(f'<div class="feat"><div class="fi">{i}</div><h4>{t}</h4><p>{d}</p></div>' for i,t,d in feats)
        body = (f'<div class="container"><section class="land"><span class="eyebrow">Full-service digital agency</span>'
                f'<h1>Your idea, shipped by Mapt</h1><p class="lead">Websites, brands, marketing and AI automation — '
                f'fast and text-first. This whole news network was built and runs on Mapt.</p>'
                f'<a class="btn-lg" href="{MAPT_URL}">Start a project →</a></section>'
                f'<div class="features">{fh}</div></div>')
        return (_head("Mapt — Websites, Branding, Marketing & AI Automation",
                      "Mapt is a full-service digital agency building websites, brands and AI automation, fast and text-first.",
                      f"{SITE_URL}/mapt.html") + _header(all_posts) + body + _footer(all_posts))
    feats = [("🧘","Daily Wellbeing","Check in on mood, energy and habits in seconds."),
             ("🤖","AI Insights","Personalized nudges powered by AI, tuned to you."),
             ("🔥","Habit Streaks","Build routines that stick with gentle reminders."),
             ("📊","Visible Progress","Simple trends that show change adding up."),
             ("🔒","Private by Design","Your data stays yours. Calm and focused."),
             ("💚","Free to Start","Begin today at no cost.")]
    fh = "".join(f'<div class="feat"><div class="fi">{i}</div><h4>{t}</h4><p>{d}</p></div>' for i,t,d in feats)
    body = (f'<div class="container"><section class="land"><span class="eyebrow">AI wellness companion</span>'
            f'<h1>Feel better, one day at a time</h1><p class="lead">Vita is your pocket wellness coach — track '
            f'habits and mood, get personalized AI insights. Calm, simple, free to start.</p>'
            f'<a class="btn-lg green" href="{VITA_URL}">Discover Vita →</a></section><div class="features">{fh}</div></div>')
    return (_head("Vita — Your AI Wellness Companion",
                  "Vita is an AI wellness app to track habits and mood and get personalized insights. Free to start.",
                  f"{SITE_URL}/vita.html") + _header(all_posts) + body + _footer(all_posts))


def static_page(title, canonical, inner, all_posts):
    body = f'<div class="container"><div class="layout"><div class="maincol"><article class="post"><h1>{title}</h1><div class="body">{inner}</div></article></div>{sidebar(all_posts, {})}</div></div>'
    return _head(f"{title} — {BRAND}", f"{title} — {BRAND}", canonical) + _header(all_posts) + body + _footer(all_posts)


def redirect_page(target):
    return (f'<!DOCTYPE html><html><head><meta charset="UTF-8"><meta http-equiv="refresh" content="0; url={target}">'
            f'<link rel="canonical" href="{target}"><title>Moved</title></head><body>Moved to <a href="{target}">{target}</a>.</body></html>')


def sitemap(urls):
    b = "".join(f"\n  <url><loc>{u}</loc><changefreq>daily</changefreq></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{b}\n</urlset>'


# ─────────── build ───────────
def _write(path, content):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    per_niche, all_posts, counts = {}, [], {}
    for niche in PODCASTS:
        ps = sorted(build_posts(niche) + build_web_posts(niche),
                    key=lambda p: _iso(p["pubDate"]), reverse=True)
        per_niche[niche["id"]] = ps
        all_posts.extend(ps)
        counts[niche["id"]] = len(ps)

    urls = [f"{SITE_URL}/", f"{SITE_URL}/mapt.html", f"{SITE_URL}/vita.html",
            f"{SITE_URL}/about.html", f"{SITE_URL}/privacy.html"]

    for niche in PODCASTS:
        nid = niche["id"]; ps = per_niche[nid]
        bd = f"blog/{nid}"
        if os.path.isdir(bd):
            for old in os.listdir(bd):
                if old.endswith(".html"):
                    os.remove(os.path.join(bd, old))
        _write(f"blog/{nid}/index.html", category_page(niche, ps, all_posts, counts))
        urls.append(f"{SITE_URL}/blog/{nid}/")
        for p in ps:
            _write(p["path"], post_page(p, all_posts, counts))
            urls.append(p["url"])
        _write(f"podcasts/{nid}/index.html", redirect_page(f"{SITE_URL}/blog/{nid}/"))
        print(f"[page] blog/{nid}/ ({len(ps)} posts)")

    _write("index.html", home_page(all_posts, per_niche, counts))
    _write("mapt.html", landing("mapt", all_posts))
    _write("vita.html", landing("vita", all_posts))

    about = ("<p><strong>Mapt Daily</strong> publishes daily news and analysis across seven beats — AI &amp; tech, "
             "finance, health, startups, crypto, world affairs and true crime — each paired with a five-minute audio "
             f'brief. Summaries are AI-assisted from public news sources, published twice a day. A project of <a href="{MAPT_URL}">Mapt</a>.</p>')
    privacy = ("<p>Mapt Daily does not collect personal information directly. Third-party services (analytics and, where "
               "present, advertising partners such as Google) may set cookies under their own policies. You can opt out of "
               "personalized ads via Google Ads Settings. Contact: hunk1.on11@gmail.com.</p>")
    _write("about.html", static_page("About Mapt Daily", f"{SITE_URL}/about.html", about, all_posts))
    _write("privacy.html", static_page("Privacy Policy", f"{SITE_URL}/privacy.html", privacy, all_posts))
    _write("sitemap.xml", sitemap(urls))
    _write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    print(f"[page] home + mapt + vita + about + privacy + sitemap ({len(urls)} urls)")


if __name__ == "__main__":
    main()
