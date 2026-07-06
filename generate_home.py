# -*- coding: utf-8 -*-
"""
generate_home.py — build the Mapt Daily mega-menu homepage (index.html)
from the freshly generated blog/ pages. Run AFTER generate_pages.py so the
homepage slider + latest-blog blocks always reflect the newest episodes.

Self-contained: CSS comes from home_style.html; article data is parsed from
blog/<cat>/ep*.html (title / dek / date / image / link).
"""
import re, glob, os
from site_header import header_html, HEADER_CSS, HEADER_JS, analytics_head

ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.join(ROOT, "blog")
OUT  = os.path.join(ROOT, "index.html")
STYLE = open(os.path.join(ROOT, "home_style.html"), encoding="utf-8").read()

CATS = ["ai-tech","finance","health","startup","crypto","world-news","true-crime"]
LABEL = {"ai-tech":"AI & Tech","finance":"Finance","health":"Health","startup":"Startups",
         "crypto":"Crypto","world-news":"World","true-crime":"True Crime"}
COLOR = {"ai-tech":"#7c3aed","finance":"#16a34a","health":"#0891b2","startup":"#e11d48",
         "crypto":"#d97706","world-news":"#2563eb","true-crime":"#111827"}

def parse(cat):
    out=[]
    d=os.path.join(BLOG,cat)
    if not os.path.isdir(d): return out
    files=[p for p in glob.glob(os.path.join(d,"*.html")) if os.path.basename(p)!="index.html"]
    for f in files:
        t=open(f,encoding="utf-8").read()
        def g(p,dv=""):
            m=re.search(p,t,re.S); return m.group(1).strip() if m else dv
        img=re.search(r'<div class="lead-img"><img src="(.*?)"',t)
        out.append({
            "cat":cat,"label":LABEL[cat],"color":COLOR[cat],
            "title":g(r'<h1>(.*?)</h1>'),
            "dek":g(r'<p class="dek">(.*?)</p>'),
            "date":g(r'🕔\s*(\d{4}-\d{2}-\d{2})'),
            "img":img.group(1) if img else "",
            "link":"/blog/%s/%s"%(cat,os.path.basename(f)),
        })
    out.sort(key=lambda a:a["date"], reverse=True)   # newest first (episode + web posts)
    return out

ARTS={c:parse(c) for c in CATS}
COUNTS={c:len(ARTS[c]) for c in CATS}
def recent(cat,n=None):
    r=ARTS[cat]; return r[:n] if n else r
ALL=sorted([a for c in CATS for a in ARTS[c]], key=lambda x:x["date"], reverse=True)

def fdate(d):
    from datetime import datetime
    try: return datetime.strptime(d,"%Y-%m-%d").strftime("%b %d, %Y")
    except: return d

def tag(a,extra=""):
    return f'<span class="cat-tag" style="background:{a["color"]}{extra}">{a["label"]}</span>'

# ---------- mega menus ----------
def mega_cards(cat, r0=False):
    cards="".join(
        f'<a class="mcard" href="{a["link"]}"><div class="thumb" style="background-image:url(\'{a["img"]}\')"></div>'
        f'<h4>{a["title"]}</h4><div class="meta">◷ {fdate(a["date"])}</div></a>'
        for a in recent(cat,4))
    return f'<div class="mega{" r0" if r0 else ""}"><ul class="subcats">' \
           f'<li class="on"><a href="/blog/{cat}/">All {LABEL[cat]}</a></li>' \
           + f'</ul><div class="mcards">{cards}</div></div>'

def mega_feat(cat, r0=False):
    r=recent(cat,5); big=r[0]; rest=r[1:5]
    fl="".join(
        f'<a class="fl" href="{a["link"]}"><div class="t" style="background-image:url(\'{a["img"]}\')"></div>'
        f'<div><h4>{a["title"]}</h4><div class="meta">◷ {fdate(a["date"])}</div></div></a>' for a in rest)
    return f'<div class="mega feat{" r0" if r0 else ""}">' \
           f'<a class="fbig" href="{big["link"]}" style="background-image:url(\'{big["img"]}\')">' \
           f'<div class="cap"><span class="cat" style="background:{big["color"]}">{big["label"]}</span><h3>{big["title"]}</h3></div></a>' \
           f'<div class="flist">{fl}</div></div>'

def menu():
    items=['<li class="active"><a href="/">Home</a></li>']
    megas={"ai-tech":mega_feat,"crypto":mega_feat}
    for i,c in enumerate(CATS):
        r0 = i>=4
        mk = megas.get(c, mega_cards)
        items.append(f'<li><a href="/blog/{c}/">{LABEL[c]} <span class="car">▾</span></a>{mk(c,r0)}</li>')
    return "".join(items)

# ---------- sections ----------
def hero():
    a,b,c=ALL[0],ALL[1],ALL[2]
    return f'''<div class="hero">
    <a class="h-big" href="{a['link']}" style="background-image:url('{a['img']}')">
      <div class="cap">{tag(a)}<h2>{a['title']}</h2><div class="meta">✍ Mapt Newsroom · ◷ {fdate(a['date'])}</div></div></a>
    <div class="h-right">
      <a class="h-s" href="{b['link']}" style="background-image:url('{b['img']}')"><span class="badge">5<small>min</small></span>
        <div class="cap">{tag(b)}<h3>{b['title']}</h3><div class="meta">◷ {fdate(b['date'])}</div></div></a>
      <a class="h-s" href="{c['link']}" style="background-image:url('{c['img']}')">
        <div class="cap">{tag(c)}<h3>{c['title']}</h3><div class="meta">◷ {fdate(c['date'])}</div></div></a>
    </div></div>'''

def plist(items,cls="pl"):
    rows=""
    for i,a in enumerate(items):
        last=' style="border-bottom:none"' if i==len(items)-1 else ''
        top=' style="padding-top:0"' if i==0 else ''
        st=(top or last)
        rows+=f'<a class="{cls}" href="{a["link"]}"{st}><div class="t" style="background-image:url(\'{a["img"]}\')"></div>' \
              f'<div><h3>{a["title"]}</h3><div class="meta">◷ {fdate(a["date"])}</div></div></a>'
    return rows

def trending():
    feat=ALL[3]; lst=ALL[4:8]
    return f'''<div class="bhead" style="background:#fff;border:1px solid var(--line);border-bottom:none;border-radius:4px 4px 0 0"><h2>Trending News</h2>
        <div class="tabs"><a class="on">Latest</a><a>AI &amp; Tech</a><a>Finance</a><a>Crypto</a></div>
        <div class="nav"><span>‹</span><span>›</span></div></div>
      <div style="background:#fff;border:1px solid var(--line);border-top:none;border-radius:0 0 4px 4px;padding:16px;margin-bottom:22px">
        <div class="split">
          <a class="tr-featured" href="{feat['link']}" style="min-height:340px;margin:0;background-image:url('{feat['img']}')">
            <div class="cap">{tag(feat)}<h2>{feat['title']}</h2><div class="meta">✍ Mapt Newsroom · ◷ {fdate(feat['date'])}</div></div></a>
          <div class="postlist" style="align-self:stretch">{plist(lst)}</div>
        </div></div>'''

def dark_block(cat):
    r=recent(cat,5); big=r[0]; lst=r[1:5]
    items=""
    for i,a in enumerate(lst):
        last=' style="border-bottom:none"' if i==len(lst)-1 else ''
        items+=f'<a class="sp-item" href="{a["link"]}"{last}><div class="t" style="background-image:url(\'{a["img"]}\')"></div>' \
               f'<div><h4>{a["title"]}</h4><div class="meta">◷ {fdate(a["date"])}</div></div></a>'
    return f'''<div class="darkblk">
        <div class="bhead"><h2>{LABEL[cat]}</h2><div class="tabs"><a class="on">All</a></div><div class="nav"><span>‹</span><span>›</span></div></div>
        <div class="body">
          <a class="sp-big" href="{big['link']}" style="background-image:url('{big['img']}')">
            <div class="cap">{tag(big)}<h3>{big['title']}</h3><div class="meta">◷ {fdate(big['date'])}</div><span class="btn-more">Read More +</span></div></a>
          <div class="sp-list">{items}</div></div></div>'''

def duo(a,b):
    def col(cat):
        r=recent(cat,3); big=r[0]; subs=r[1:3]
        mini="".join(
            f'<a class="mini" href="{x["link"]}"><div class="t" style="background-image:url(\'{x["img"]}\')"></div>'
            f'<div><h4>{x["title"]}</h4><div class="meta">◷ {fdate(x["date"])}</div></div></a>' for x in subs)
        return f'''<div class="blk" style="border:none;background:none">
          <div class="bhead" style="padding-left:0;padding-right:0;background:none"><h2>{LABEL[cat]}</h2><div class="nav"><span>‹</span><span>›</span></div></div>
          <a class="colpost" href="{big['link']}" style="display:block;padding-top:16px">
            <div class="img" style="background-image:url('{big['img']}')">{tag(big)}</div>
            <h3>{big['title']}</h3><p>{big['dek'][:120]}…</p><span class="btn-more">Read More +</span></a>
          <div class="colsub">{mini}</div></div>'''
    return f'<div class="two">{col(a)}{col(b)}</div>'

def banner(cat):
    r=recent(cat,2)
    return '<div class="fbanner">'+ "".join(
        f'<a class="fbn" href="{a["link"]}" style="background-image:url(\'{a["img"]}\')">'
        f'<div class="cap">{tag(a)}<h3>{a["title"]}</h3><div class="meta">◷ {fdate(a["date"])}</div></div></a>' for a in r)+'</div>'

def tech_block(cat):
    r=recent(cat,5); big=r[0]; lst=r[1:5]
    return f'''<div class="blk" style="border:none;background:none">
      <div class="bhead" style="padding-left:0;padding-right:0;background:none"><h2>{LABEL[cat]}</h2>
        <div class="tabs"><a class="on">All</a></div><div class="nav"><span>‹</span><span>›</span></div></div>
      <div class="split" style="padding-top:16px">
        <a class="colpost" href="{big['link']}" style="display:block">
          <div class="img" style="background-image:url('{big['img']}')">{tag(big)}</div>
          <h3>{big['title']}</h3><p>{big['dek'][:120]}…</p><span class="btn-more">Read More +</span></a>
        <div class="postlist">{plist(lst)}</div></div></div>'''

def mini_list(items,title):
    rows=""
    for i,a in enumerate(items):
        last=' style="border-bottom:none"' if i==len(items)-1 else ''
        rows+=f'<a class="mini" href="{a["link"]}"{last}><div class="t" style="background-image:url(\'{a["img"]}\')"></div>' \
              f'<div><h4>{a["title"]}</h4><div class="meta">◷ {fdate(a["date"])}</div></div></a>'
    return f'<div class="w tabbed"><div class="w-title">{title}</div>{rows}</div>'

def sidebar_follow():
    return '''<div class="w"><div class="w-title">Follow Us</div>
        <div class="meta" style="margin:-8px 0 12px"><span>Join <b style="color:var(--txt)">6.2K</b> Followers</span></div>
        <div class="follow">
          <a class="fb"><span>f</span><span><b>1.2K</b>Fans</span></a>
          <a class="tw"><span>𝕏</span><span><b>480</b>Followers</span></a>
          <a class="yt"><span>▶</span><span><b>2.1K</b>Subscribers</span></a>
          <a class="ig"><span>◎</span><span><b>760</b>Followers</span></a>
        </div></div>
      <div class="w"><div class="weatherw">
          <div class="top"><div><div class="c">Sydney</div><div class="sub2">Clear Sky</div></div><div class="deg">24<sup>℃</sup></div><div class="ico-big">☀</div></div>
          <div class="sub2" style="margin-top:8px">↑ 27℃ · ↓ 18℃ · 💧 30% · 🌬 12 km/h</div>
          <div class="days"><div>Fri<div class="dico">⛅</div>25℃</div><div>Sat<div class="dico">☀</div>27℃</div><div>Sun<div class="dico">☁</div>22℃</div><div>Mon<div class="dico">🌧</div>20℃</div></div>
        </div></div>'''

def videos_block(cat):
    r=recent(cat,4); big=r[0]; small=r[1:4]
    vr="".join(f'<a class="vid-s" href="{a["link"]}" style="background-image:url(\'{a["img"]}\')"><span class="play">▶</span></a>' for a in small)
    return f'''<div class="blk" style="border:none;background:none">
      <div class="bhead" style="padding-left:0;padding-right:0;background:none"><h2>Latest Episodes</h2><div class="nav"><span>‹</span><span>›</span></div></div>
      <a class="vid-big" href="{big['link']}" style="background-image:url('{big['img']}');margin-top:16px"><span class="play">▶</span>
        <div class="cap">{tag(big)}<h3>{big['title']}</h3><div class="meta">🎧 Listen · 5 min · ◷ {fdate(big['date'])}</div></div></a>
      <div class="vid-row">{vr}</div></div>'''

def categories_widget():
    icons={"ai-tech":"💻","finance":"💹","health":"➕","startup":"🚀","crypto":"₿","world-news":"🌐","true-crime":"🔍"}
    rows="".join(
        f'<a href="/blog/{c}/"><span class="ci" style="background:{COLOR[c]}">{icons[c]}</span><h4>{LABEL[c]}</h4><span class="cnt">{COUNTS[c]}</span></a>'
        for c in CATS)
    return f'<div class="w"><div class="w-title">Categories</div><div class="catlist">{rows}</div></div>'

def whatsnew():
    items=ALL[8:12]
    cells=""
    for i,a in enumerate(items):
        border='padding:0 0 20px;border:none' if i<2 else 'padding:20px 0 0;border-top:1px solid var(--line)'
        cells+=f'''<a class="pl" href="{a['link']}" style="{border}"><div class="t" style="width:180px;height:120px;background-image:url('{a['img']}')"></div>
          <div>{tag(a)}<h3 style="margin:8px 0">{a['title']}</h3><p style="color:var(--muted);font-size:12.5px">{a['dek'][:110]}…</p>
          <div class="meta">✍ Mapt Newsroom · ◷ {fdate(a['date'])}</div></div></a>'''
    return f'''<div class="bhead" style="background:#fff;border:1px solid var(--line);border-radius:4px 4px 0 0"><h2>What's New</h2><div class="nav"><span>‹</span><span>›</span></div></div>
  <div style="background:#fff;border:1px solid var(--line);border-top:none;border-radius:0 0 4px 4px;padding:22px;margin-bottom:22px">
    <div class="wn-grid">{cells}</div><button class="load">Load More</button></div>'''

def foot_posts(items):
    return "".join(
        f'<a class="fpost" href="{a["link"]}"><div class="t" style="background-image:url(\'{a["img"]}\')"></div>'
        f'<div><h5>{a["title"]}</h5><div class="meta">◷ {fdate(a["date"])}</div></div></a>' for a in items)

def breaking():
    top=ALL[:5]
    lis="".join(f'<li>{a["title"]}</li>' for a in top)
    return lis+lis

# ---------- assemble ----------
_CATARTS = {c:[{"title":a["title"],"href":a["link"],"img":a["img"],"date":fdate(a["date"])}
               for a in recent(c,4)] for c in CATS}
HEADER = header_html(_CATARTS, active="home", breaking=[a["title"] for a in ALL[:5]])

HTML = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Mapt Daily — AI, Finance, Health, Startups, Crypto, World &amp; True Crime news</title>
<meta name="description" content="Mapt Daily — your free daily brief on AI &amp; tech, finance, health, startups, crypto, world news and true crime. Short, fast, updated every morning." />
<meta property="og:title" content="Mapt Daily" />
<meta property="og:description" content="Free daily news across AI, finance, health, startups, crypto, world &amp; true crime." />
<meta property="og:type" content="website" />
<link rel="canonical" href="https://daily.mapt.cloud/" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&family=Roboto+Condensed:wght@700&display=swap" rel="stylesheet" />
{STYLE}
{HEADER_CSS}
{analytics_head()}
</head>
<body>

{HEADER}

<div class="container">
  {hero()}
  <div class="grid-main">
    <div>
      {trending()}
      {dark_block("true-crime")}
      {duo("finance","health")}
    </div>
    <aside>
      {sidebar_follow()}
      {mini_list(ALL[:5],"Recent")}
    </aside>
  </div>
</div>

<div class="container">{banner("world-news")}</div>

<div class="container">
  <div class="grid-main">
    {tech_block("ai-tech")}
    <aside>{mini_list(recent("startup",4),"Most Viewed")}</aside>
  </div>
</div>

<div class="container">
  <div class="grid-main">
    {videos_block("crypto")}
    <aside>
      <div class="subs"><h3>Get the Mapt Daily brief</h3><p>The day's top stories across every topic — free, every morning.</p>
        <form id="subForm"><input type="email" placeholder="Your email address" required /><button>Subscribe</button></form></div>
      {categories_widget()}
    </aside>
  </div>
</div>

<div class="container">
  <a class="adbox" href="https://mapt.cloud" style="margin-bottom:22px"><div class="lbl"><b>ADS</b><span>728 X 90</span></div><div class="vr"></div><div class="txt">Mapt — Build. Automate. Grow. Websites, apps &amp; AI automation for AU &amp; NZ.</div><span class="btn">Free audit →</span></a>
</div>

<div class="container">{whatsnew()}</div>

<footer>
  <div class="ftop"><div class="wrap"><div class="fgrid">
    <div><h4>Most Viewed Posts</h4>{foot_posts(ALL[:3])}</div>
    <div><h4>Latest Posts</h4>{foot_posts(ALL[3:6])}</div>
    <div><h4>Topics</h4><div class="ftags">{"".join(f'<a href="/blog/{c}/">{LABEL[c]}</a>' for c in CATS)}<a href="#">Podcast</a><a href="#">Daily brief</a><a href="#">Anthropic</a><a href="#">Bitcoin</a></div></div>
    <div><h4>Follow Us</h4><div class="fsoc">
      <a style="background:#3b5998"><span>f</span> Facebook</a>
      <a style="background:#111"><span>𝕏</span> Twitter</a>
      <a style="background:#c4302b"><span>▶</span> YouTube</a>
      <a style="background:#c13584"><span>◎</span> Instagram</a></div></div>
  </div></div></div>
  <div class="fbottom"><div class="wrap">
    <a href="/" class="logo-main"><span class="mk">M</span>Mapt<small>daily</small></a>
    <form class="fsub" id="subForm2"><input type="email" placeholder="Your email address" required /><button>Subscribe</button></form>
  </div></div>
  <div class="copy"><div class="wrap">
    <span>© <span id="yr"></span> Mapt Daily — a project of <a href="https://mapt.cloud" style="margin:0">Mapt</a>. AI-assisted summaries from public news sources.</span>
    <div class="fmenu"><a href="/about.html">About</a><a href="/privacy.html">Privacy</a><a href="/mapt.html">Mapt</a><a href="mailto:hello@mapt.cloud">Contact</a></div>
  </div></div>
</footer>

<script>
  document.getElementById('yr').textContent=new Date().getFullYear();
  ['subForm','subForm2'].forEach(function(id){{
    var f=document.getElementById(id); if(!f) return;
    f.addEventListener('submit',function(ev){{
      ev.preventDefault();
      var email=f.querySelector('input').value;
      fetch('/subscribe.php',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:'email='+encodeURIComponent(email)+'&source=home'}})
        .then(function(r){{return r.ok?r.text():Promise.reject();}})
        .then(function(){{f.innerHTML='<p style="color:#16a34a;font-weight:700;margin:0">✓ Thanks — you are subscribed!</p>';}})
        .catch(function(){{window.location.href='mailto:hello@mapt.cloud?subject='+encodeURIComponent('Subscribe: Mapt Daily')+'&body='+encodeURIComponent('Please subscribe: '+email);}});
    }});
  }});
</script>
{HEADER_JS}
</body>
</html>'''

if __name__ == "__main__":
    open(OUT,"w",encoding="utf-8").write(HTML)
    print("Wrote",OUT,"| articles:",len(ALL),"| categories:",{c:COUNTS[c] for c in CATS})
