# -*- coding: utf-8 -*-
"""
site_header.py — ONE shared Mapt Daily header (mega-menu) used by BOTH the
homepage (generate_home.py) and every blog/category/post/static page
(generate_pages.py). Fully namespaced with `mh-` so it never collides with
static/site.css or the homepage body styles. Includes a working mobile menu.

Usage:
    from site_header import header_html, HEADER_CSS, HEADER_JS
    ...<head> ... {HEADER_CSS} ...
    <body>{header_html(cat_arts, active='ai-tech')} ...
    ... {HEADER_JS}</body>

cat_arts: {cat_id: [ {"title","href","img","date"}, ... ]}  (4 recent is enough)
"""
import html as _html

CATS  = ["ai-tech","finance","health","startup","crypto","world-news","true-crime"]
LABEL = {"ai-tech":"AI & Tech","finance":"Finance","health":"Health","startup":"Startups",
         "crypto":"Crypto","world-news":"World","true-crime":"True Crime"}
COLOR = {"ai-tech":"#7c3aed","finance":"#16a34a","health":"#0891b2","startup":"#e11d48",
         "crypto":"#d97706","world-news":"#2563eb","true-crime":"#111827"}
FEAT  = {"ai-tech","crypto"}   # these two use the big-featured mega style


def _mega(cat, arts, right=False):
    arts = (arts or [])[:5]
    r0 = " mh-r0" if right else ""
    if cat in FEAT and arts:
        big = arts[0]; rest = arts[1:5]
        fl = "".join(
            f'<a class="mh-fl" href="{a["href"]}"><span class="mh-t" style="background-image:url(\'{a["img"]}\')"></span>'
            f'<span><b>{_html.escape(a["title"])}</b><i>◷ {a["date"]}</i></span></a>' for a in rest)
        return (f'<div class="mh-mega mh-feat{r0}">'
                f'<a class="mh-fbig" href="{big["href"]}" style="background-image:url(\'{big["img"]}\')">'
                f'<span class="mh-cap"><em style="background:{COLOR[cat]}">{LABEL[cat]}</em>'
                f'<b>{_html.escape(big["title"])}</b></span></a><div class="mh-fl-wrap">{fl}</div></div>')
    cards = "".join(
        f'<a class="mh-card" href="{a["href"]}"><span class="mh-th" style="background-image:url(\'{a["img"]}\')"></span>'
        f'<b>{_html.escape(a["title"])}</b><i>◷ {a["date"]}</i></a>' for a in arts[:4])
    return (f'<div class="mh-mega{r0}"><div class="mh-sub"><a href="/blog/{cat}/">All {LABEL[cat]}</a></div>'
            f'<div class="mh-cards">{cards}</div></div>')


def header_html(cat_arts, active="home", breaking=None):
    cat_arts = cat_arts or {}
    ac = ' mh-active' if active == "home" else ''
    items = [f'<li class="mh-has{ac}"><a href="/">Home</a></li>']
    for i, c in enumerate(CATS):
        a = ' mh-active' if active == c else ''
        items.append(
            f'<li class="mh-drop{a}"><a href="/blog/{c}/">{LABEL[c]} <span class="mh-car">▾</span></a>'
            f'{_mega(c, cat_arts.get(c), right=i>=4)}</li>')
    menu = "".join(items)
    brk = breaking or ["Mapt Daily — fresh tech, finance, health, startup, crypto & world news every day"]
    ticks = "".join(f'<span>{_html.escape(t)}</span>' for t in (brk * 2))
    return f"""<div class="mh-top"><div class="mh-in">
    <span class="mh-date" id="mhDate">Today</span>
    <div class="mh-brk"><span class="mh-lbl">Breaking</span><div class="mh-tick"><div class="mh-run">{ticks}</div></div></div>
    <div class="mh-soc"><a aria-label="Facebook">f</a><a aria-label="X">𝕏</a><a aria-label="Instagram">◎</a><a aria-label="YouTube">▶</a><a aria-label="LinkedIn">in</a></div>
  </div></div>
  <div class="mh-bar">
  <div class="mh-in">
    <a class="mh-logo" href="/"><span class="mh-mk">M</span>Mapt<small>daily</small></a>
    <a class="mh-ad" href="https://mapt.cloud"><span class="mh-adtag">Sponsored</span>
      <span class="mh-adtxt">Need a site like this? <b>Mapt</b> builds websites, brands &amp; growth engines.</span>
      <span class="mh-cta">Get Mapt →</span></a>
  </div>
</div>
<header class="mh-nav" id="mhNav">
  <div class="mh-in">
    <button class="mh-burger" id="mhBurger" type="button" aria-label="Open menu">☰</button>
    <ul class="mh-menu" id="mhMenu">
      <li class="mh-mhead"><span>Menu</span><button class="mh-close" id="mhClose" type="button" aria-label="Close menu">✕</button></li>
      {menu}
    </ul>
    <div class="mh-tools">
      <span class="mh-wx">☀ 24°</span>
      <button class="mh-ico" id="mhTheme" type="button" aria-label="Toggle theme">◐</button>
      <input class="mh-search" placeholder="Search…" aria-label="Search" />
    </div>
  </div>
</header>
<div class="mh-overlay" id="mhOverlay"></div>"""


HEADER_CSS = """<style>
.mh-top,.mh-bar,.mh-nav,.mh-menu,.mh-mega,.mh-overlay,.mh-top *,.mh-bar *,.mh-nav *{box-sizing:border-box}
.mh-top{background:#fff;border-bottom:1px solid #e9ebee;font-family:Roboto,Arial,sans-serif}
.mh-top .mh-in{height:42px;gap:14px}
.mh-date{font-size:12px;color:#8a929b;white-space:nowrap;font-weight:500}
.mh-brk{display:flex;align-items:center;gap:12px;flex:1;min-width:0;overflow:hidden}
.mh-lbl{background:#e8443b;color:#fff;font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:5px 10px;white-space:nowrap}
.mh-tick{overflow:hidden;flex:1;min-width:0}
.mh-run{display:flex;gap:56px;white-space:nowrap;width:max-content;animation:mhrun 30s linear infinite}
.mh-run span{font-size:12.5px;color:#3a3f46;white-space:nowrap}
.mh-tick:hover .mh-run{animation-play-state:paused}
@keyframes mhrun{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.mh-soc{display:flex;gap:10px}
.mh-soc a{color:#6a727b;font-size:13px;text-decoration:none;cursor:pointer}
.mh-soc a:hover{color:#4a90d9}
.mh-bar{background:#fff;border-bottom:1px solid #e9ebee}
.mh-in{max-width:1200px;margin:0 auto;padding:0 16px;display:flex;align-items:center;gap:20px}
.mh-bar .mh-in{justify-content:space-between;padding:16px}
.mh-logo{font-family:'Roboto Condensed','Arial Narrow',sans-serif;font-size:34px;font-weight:700;letter-spacing:-.5px;color:#20232a;display:flex;align-items:center;text-decoration:none;line-height:1}
.mh-logo .mh-mk{width:34px;height:34px;display:inline-grid;place-items:center;background:#4a90d9;color:#fff;border-radius:8px;font-size:19px;margin-right:9px;font-family:Roboto,Arial,sans-serif}
.mh-logo small{font-size:17px;font-weight:400;color:#9aa1a9;text-transform:lowercase}
.mh-ad{display:flex;align-items:center;gap:16px;max-width:640px;height:74px;padding:0 22px;border-radius:6px;background:#1b1e24;color:#fff;text-decoration:none;overflow:hidden}
.mh-adtag{font-size:10px;letter-spacing:.15em;color:#5fa0e6;text-transform:uppercase;font-weight:700}
.mh-adtxt{font-size:14px;font-weight:600;line-height:1.35}.mh-adtxt b{color:#5fa0e6}
.mh-cta{margin-left:auto;background:#4a90d9;color:#fff;font-weight:700;font-size:12px;padding:10px 16px;border-radius:5px;white-space:nowrap;text-transform:uppercase}

.mh-nav{position:sticky;top:0;z-index:500;background:#1b1e24;box-shadow:0 2px 12px rgba(0,0,0,.2)}
.mh-nav .mh-in{display:flex;align-items:stretch;height:50px;gap:0}
.mh-menu{display:flex;align-items:stretch;list-style:none;height:100%;margin:0;padding:0}
.mh-menu>li{position:relative;display:flex;align-items:center}
.mh-menu>li>a{display:flex;align-items:center;gap:6px;height:100%;padding:0 16px;color:#e6e9ec;font:700 13px/1 Roboto,Arial,sans-serif;letter-spacing:.03em;text-transform:uppercase;text-decoration:none;transition:.15s}
.mh-menu>li>a .mh-car{font-size:9px;opacity:.75}
.mh-menu>li.mh-active>a{background:#4a90d9;color:#fff}
.mh-menu>li:hover>a{background:#26292e;color:#fff}
.mh-mhead{display:none}
.mh-tools{margin-left:auto;display:flex;align-items:center;gap:12px;color:#c7ccd2}
.mh-wx{font-size:12.5px;color:#e6e9ec;white-space:nowrap}
.mh-ico{background:none;border:none;color:#aab1b8;font-size:15px;cursor:pointer;line-height:1}
.mh-ico:hover{color:#fff}
.mh-search{background:#2f343b;border:none;border-radius:100px;padding:8px 14px;color:#e6e9ec;font-size:12.5px;min-width:150px;outline:none;font-family:inherit}
.mh-search::placeholder{color:#828a92}
.mh-burger{display:none;background:none;border:none;color:#fff;font-size:21px;cursor:pointer;padding:0 14px;align-items:center}
.mh-close{display:none}
.mh-overlay{display:none}

.mh-mega{position:absolute;top:100%;left:0;background:#1b1e24;border-top:3px solid #4a90d9;min-width:720px;padding:20px;display:grid;grid-template-columns:170px 1fr;gap:18px;opacity:0;visibility:hidden;transform:translateY(6px);transition:.16s;box-shadow:0 24px 46px rgba(0,0,0,.45);z-index:520}
.mh-menu>li:hover .mh-mega{opacity:1;visibility:visible;transform:none}
.mh-mega.mh-r0{left:auto;right:0}
.mh-mega .mh-sub{border-right:1px solid #33373e;padding-right:8px}
.mh-mega .mh-sub a{display:block;padding:9px 11px;border-radius:5px;color:#5fa0e6;font-size:13px;font-weight:600;text-decoration:none}
.mh-mega .mh-sub a:hover{background:#26292e}
.mh-cards{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.mh-card{text-decoration:none}
.mh-card .mh-th{display:block;border-radius:5px;height:96px;background-size:cover;background-position:center;margin-bottom:9px}
.mh-card b{display:block;font-size:13px;color:#eceff2;font-weight:500;line-height:1.35}
.mh-card:hover b{color:#5fa0e6}
.mh-card i{display:block;font-size:11px;color:#828a92;margin-top:5px;font-style:normal}
.mh-feat{grid-template-columns:1.1fr 1fr}
.mh-fbig{position:relative;border-radius:6px;overflow:hidden;min-height:200px;background-size:cover;background-position:center;display:flex;align-items:flex-end;text-decoration:none}
.mh-fbig:after{content:"";position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,.85),transparent 60%)}
.mh-fbig .mh-cap{position:relative;z-index:2;padding:16px}
.mh-fbig em{display:inline-block;font-style:normal;color:#fff;font-size:9px;font-weight:700;text-transform:uppercase;padding:4px 8px;border-radius:3px;margin-bottom:8px}
.mh-fbig b{display:block;color:#fff;font-size:16px;line-height:1.25}
.mh-fl-wrap{display:flex;flex-direction:column;gap:12px}
.mh-fl{display:flex;gap:11px;text-decoration:none}
.mh-fl .mh-t{width:70px;height:52px;border-radius:5px;flex:none;background-size:cover;background-position:center}
.mh-fl b{display:block;font-size:12.5px;color:#eceff2;font-weight:500;line-height:1.3}
.mh-fl:hover b{color:#5fa0e6}
.mh-fl i{display:block;font-size:10.5px;color:#828a92;margin-top:4px;font-style:normal}

@media(max-width:1080px){.mh-ad{display:none}}
@media(max-width:900px){
  .mh-burger{display:flex}
  .mh-tools .mh-wx,.mh-search{display:none}
  .mh-brk{display:none}
  .mh-top .mh-in{justify-content:space-between}
  .mh-menu{position:fixed;top:0;left:0;bottom:0;width:280px;max-width:84vw;background:#1b1e24;padding:0 0 24px;overflow-y:auto;z-index:1000;transform:translateX(-100%);transition:transform .25s;display:block}
  .mh-menu.mh-open{transform:none}
  .mh-mhead{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid #33373e;color:#fff;font-weight:700;position:sticky;top:0;background:#1b1e24}
  .mh-close{display:block;background:none;border:none;color:#fff;font-size:20px;cursor:pointer}
  .mh-menu>li{width:100%;display:block}
  .mh-menu>li>a{width:100%;padding:14px 18px}
  .mh-menu>li.mh-active>a{background:#26292e;border-left:3px solid #4a90d9}
  /* mobile: collapse each dropdown to a clean text list (no image panels) */
  .mh-mega{position:static;opacity:1;visibility:visible;transform:none;min-width:0;width:100%;display:none;box-shadow:none;border-top:none;padding:2px 18px 10px;background:#16181d}
  .mh-menu>li.mh-expand .mh-mega{display:block}
  .mh-mega .mh-fbig{display:none}
  .mh-cards,.mh-fl-wrap{display:block;grid-template-columns:1fr}
  .mh-mega .mh-th,.mh-fl .mh-t{display:none}
  .mh-card,.mh-fl{display:block;padding:9px 0;border-bottom:1px solid #2a2e35}
  .mh-card:last-child,.mh-fl:last-child{border-bottom:none}
  .mh-card b,.mh-fl b{font-size:13px;font-weight:500}
  .mh-card i,.mh-fl i{font-size:10.5px}
  .mh-mega .mh-sub{border:none;padding:0 0 6px}
  .mh-mega .mh-sub a{padding:8px 0;font-weight:700}
  .mh-overlay.mh-open{display:block;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:900}
  body.mh-lock{overflow:hidden}
}
</style>"""


HEADER_JS = """<script>
(function(){
  var d=document.getElementById('mhDate');
  if(d){try{d.textContent=new Date().toLocaleDateString('en-AU',{weekday:'long',day:'numeric',month:'long',year:'numeric'});}catch(e){}}
  var menu=document.getElementById('mhMenu'), burger=document.getElementById('mhBurger'),
      closeb=document.getElementById('mhClose'), ov=document.getElementById('mhOverlay');
  function open(){menu.classList.add('mh-open');ov.classList.add('mh-open');document.body.classList.add('mh-lock');}
  function close(){menu.classList.remove('mh-open');ov.classList.remove('mh-open');document.body.classList.remove('mh-lock');
    [].forEach.call(menu.querySelectorAll('.mh-expand'),function(li){li.classList.remove('mh-expand');});}
  if(burger)burger.addEventListener('click',function(e){e.stopPropagation();menu.classList.contains('mh-open')?close():open();});
  if(closeb)closeb.addEventListener('click',close);
  if(ov)ov.addEventListener('click',close);
  // tap a category on mobile → expand its panel instead of navigating
  [].forEach.call(menu.querySelectorAll('li.mh-drop>a'),function(a){
    a.addEventListener('click',function(e){
      if(window.innerWidth<=900){e.preventDefault();a.parentNode.classList.toggle('mh-expand');}
    });
  });
  // theme toggle — works for homepage (body.dark) and blog pages (html.dark)
  var t=document.getElementById('mhTheme');
  if(t)t.addEventListener('click',function(){document.body.classList.toggle('dark');document.documentElement.classList.toggle('dark');});
  window.addEventListener('resize',function(){if(window.innerWidth>900)close();});
  // functional subscribe forms (POST to Hostinger PHP, graceful mailto fallback)
  [].forEach.call(document.querySelectorAll('.mh-subform'),function(f){
    f.addEventListener('submit',function(ev){ev.preventDefault();
      var email=f.querySelector('input').value;
      fetch('/subscribe.php',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:'email='+encodeURIComponent(email)+'&source='+(f.getAttribute('data-source')||'blog')})
        .then(function(r){return r.ok?r.text():Promise.reject();})
        .then(function(){f.innerHTML='<p style="color:#16a34a;font-weight:700;margin:0">\\u2713 Subscribed!</p>';})
        .catch(function(){window.location.href='mailto:hello@mapt.cloud?subject=Subscribe&body='+encodeURIComponent(email);});
    });
  });
})();
</script>"""
