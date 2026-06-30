"""
Generate static HTML pages for all podcasts:
  - index.html           → hub page with all 7 podcasts
  - podcasts/<id>/index.html → individual podcast page with episodes
"""

import os
import json
from niches import PODCASTS

BASE_URL = "https://sameer1337.github.io/ai-tech-podcast"

SPOTIFY_URLS = {
    "ai-tech":    "",
    "finance":    "",
    "health":     "",
    "startup":    "",
    "crypto":     "",
    "world-news": "",
    "true-crime": "",
}

AMAZON_URLS = {
    "ai-tech":    "",
    "finance":    "",
    "health":     "",
    "startup":    "",
    "crypto":     "",
    "world-news": "",
    "true-crime": "",
}

COLORS = {
    "ai-tech":    {"bg": "#0a0a1f", "grad": "#1a0a2e", "accent": "#7c3aed", "text": "#a78bfa"},
    "finance":    {"bg": "#0a1a0a", "grad": "#0a2e0a", "accent": "#16a34a", "text": "#4ade80"},
    "health":     {"bg": "#0a1a1f", "grad": "#0a2a2e", "accent": "#0891b2", "text": "#22d3ee"},
    "startup":    {"bg": "#1a0a2e", "grad": "#2e0a4e", "accent": "#9333ea", "text": "#c084fc"},
    "crypto":     {"bg": "#1a0f00", "grad": "#2e1a00", "accent": "#d97706", "text": "#fbbf24"},
    "world-news": {"bg": "#0a0f1a", "grad": "#0a1a2e", "accent": "#1d4ed8", "text": "#60a5fa"},
    "true-crime": {"bg": "#1a0000", "grad": "#2e0000", "accent": "#dc2626", "text": "#f87171"},
}

ICONS = {
    "ai-tech":    "🤖",
    "finance":    "💰",
    "health":     "🧬",
    "startup":    "🚀",
    "crypto":     "₿",
    "world-news": "🌍",
    "true-crime": "🔍",
}


def load_episodes(niche_id):
    path = f"logs/episodes_{niche_id}.json"
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            return sorted(data, key=lambda x: x["number"], reverse=True)
    return []


def podcast_page(niche, episodes):
    pid     = niche["id"]
    c       = COLORS[pid]
    icon    = ICONS[pid]
    spotify = SPOTIFY_URLS.get(pid, "")
    amazon  = AMAZON_URLS.get(pid, "")
    feed    = f"{BASE_URL}/{niche['rss_file']}"
    cover   = niche["cover_url"]

    spotify_btn = f'<a href="{spotify}" class="badge spotify" target="_blank">🎵 Spotify</a>' if spotify else ""
    amazon_btn  = f'<a href="{amazon}" class="badge amazon" target="_blank">🎶 Amazon Music</a>' if amazon else ""

    ep_html = ""
    for ep in episodes[:20]:
        audio_url = ep.get("audio_url", "")
        ep_html += f"""
        <div class="episode">
          <div class="ep-meta">
            <span class="ep-num">EP {ep['number']}</span>
            <span class="ep-date">{ep['pubDate'][:16]}</span>
          </div>
          <div class="ep-title">{ep['title']}</div>
          <div class="ep-desc">{ep['description'][:200]}...</div>
          {"<audio controls src='" + audio_url + "'></audio>" if audio_url else ""}
        </div>"""

    if not ep_html:
        ep_html = '<div class="no-eps">Episodes coming soon — check back tomorrow!</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{niche['title']} — Free Daily Podcast</title>
  <meta name="description" content="{niche['description'][:160]}">
  <meta property="og:title" content="{niche['title']}">
  <meta property="og:description" content="{niche['description'][:160]}">
  <meta property="og:image" content="{cover}">
  <meta property="og:url" content="{BASE_URL}/podcasts/{pid}/">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="{cover}">
  <style>
    *{{ margin:0; padding:0; box-sizing:border-box; }}
    body{{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:{c['bg']}; color:#fff; }}
    a{{ color:inherit; text-decoration:none; }}

    /* NAV */
    nav{{ background:rgba(0,0,0,0.4); padding:14px 24px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #ffffff15; }}
    .nav-logo{{ font-weight:700; font-size:1rem; color:{c['text']}; }}
    .nav-back{{ font-size:0.85rem; color:#aaa; }}
    .nav-back:hover{{ color:#fff; }}

    /* BANNER */
    .banner{{
      width:100%; height:220px;
      background:linear-gradient(135deg, {c['bg']} 0%, {c['grad']} 60%, {c['accent']}33 100%);
      display:flex; align-items:center; justify-content:center;
      position:relative; overflow:hidden; border-bottom:2px solid {c['accent']}44;
    }}
    .banner-bg{{
      position:absolute; inset:0;
      background:repeating-linear-gradient(45deg, transparent, transparent 40px, {c['accent']}08 40px, {c['accent']}08 41px);
    }}
    .banner-content{{ position:relative; text-align:center; padding:20px; }}
    .banner-icon{{ font-size:3.5rem; margin-bottom:10px; display:block; }}
    .banner-title{{ font-size:2.2rem; font-weight:900; color:#fff; letter-spacing:-0.5px; }}
    .banner-sub{{ font-size:1rem; color:{c['text']}; margin-top:6px; }}

    /* HERO */
    .hero{{ display:flex; gap:32px; align-items:flex-start; max-width:900px; margin:40px auto; padding:0 24px; }}
    .cover{{ width:180px; height:180px; border-radius:16px; flex-shrink:0; box-shadow:0 12px 40px {c['accent']}55; }}
    .hero-info h1{{ font-size:1.8rem; font-weight:800; margin-bottom:10px; }}
    .hero-info p{{ color:#b0b0c0; line-height:1.7; font-size:0.95rem; margin-bottom:20px; }}
    .badges{{ display:flex; gap:12px; flex-wrap:wrap; }}
    .badge{{ display:inline-flex; align-items:center; gap:8px; padding:10px 20px; border-radius:50px; font-weight:600; font-size:0.9rem; border:1px solid #333; background:#ffffff10; transition:all 0.2s; }}
    .badge:hover{{ transform:translateY(-2px); background:#ffffff20; }}
    .badge.spotify{{ border-color:#1DB954; }}
    .badge.amazon{{ border-color:#FF9900; }}
    .badge.rss{{ border-color:{c['accent']}; }}

    /* STATS */
    .stats{{ display:flex; gap:24px; max-width:900px; margin:0 auto 40px; padding:0 24px; }}
    .stat{{ background:#ffffff08; border:1px solid #ffffff10; border-radius:12px; padding:16px 24px; flex:1; text-align:center; }}
    .stat-num{{ font-size:2rem; font-weight:800; color:{c['text']}; }}
    .stat-label{{ font-size:0.8rem; color:#777; margin-top:4px; }}

    /* EPISODES */
    .section{{ max-width:900px; margin:0 auto 60px; padding:0 24px; }}
    .section h2{{ font-size:1.3rem; font-weight:700; margin-bottom:20px; color:{c['text']}; border-left:3px solid {c['accent']}; padding-left:12px; }}
    .episode{{ background:#ffffff06; border:1px solid #ffffff0f; border-radius:12px; padding:20px; margin-bottom:16px; transition:border-color 0.2s; }}
    .episode:hover{{ border-color:{c['accent']}44; }}
    .ep-meta{{ display:flex; gap:12px; margin-bottom:8px; }}
    .ep-num{{ background:{c['accent']}22; color:{c['text']}; font-size:0.75rem; font-weight:700; padding:2px 10px; border-radius:20px; }}
    .ep-date{{ color:#666; font-size:0.8rem; }}
    .ep-title{{ font-weight:600; font-size:1rem; margin-bottom:6px; }}
    .ep-desc{{ color:#888; font-size:0.85rem; line-height:1.6; margin-bottom:12px; }}
    audio{{ width:100%; height:36px; margin-top:8px; }}
    .no-eps{{ text-align:center; color:#555; padding:40px; }}

    footer{{ text-align:center; padding:24px; color:#444; font-size:0.8rem; border-top:1px solid #ffffff10; }}
    footer a{{ color:{c['accent']}; }}

    @media(max-width:600px){{
      .hero{{ flex-direction:column; }}
      .cover{{ width:140px; height:140px; }}
      .banner-title{{ font-size:1.6rem; }}
      .stats{{ flex-wrap:wrap; }}
    }}
  </style>
</head>
<body>

<nav>
  <span class="nav-logo">{icon} {niche['title']}</span>
  <a href="{BASE_URL}/" class="nav-back">← All Podcasts</a>
</nav>

<div class="banner">
  <div class="banner-bg"></div>
  <div class="banner-content">
    <span class="banner-icon">{icon}</span>
    <div class="banner-title">{niche['title']}</div>
    <div class="banner-sub">5 Minutes · Every Morning · Free</div>
  </div>
</div>

<div class="hero">
  <img src="{cover}" alt="{niche['title']} cover" class="cover">
  <div class="hero-info">
    <h1>{niche['title']}</h1>
    <p>{niche['description']}</p>
    <div class="badges">
      {spotify_btn}
      {amazon_btn}
      <a href="{feed}" class="badge rss" target="_blank">📡 RSS Feed</a>
    </div>
  </div>
</div>

<div class="stats">
  <div class="stat">
    <div class="stat-num">{len(episodes)}</div>
    <div class="stat-label">Episodes</div>
  </div>
  <div class="stat">
    <div class="stat-num">5 min</div>
    <div class="stat-label">Per Episode</div>
  </div>
  <div class="stat">
    <div class="stat-num">Daily</div>
    <div class="stat-label">New Episodes</div>
  </div>
  <div class="stat">
    <div class="stat-num">Free</div>
    <div class="stat-label">Always</div>
  </div>
</div>

<div class="section">
  <h2>Latest Episodes</h2>
  {ep_html}
</div>

<footer>
  <p>© 2026 {niche['title']} · <a href="{feed}">RSS Feed</a> · <a href="{BASE_URL}/">All Shows</a></p>
</footer>

</body>
</html>"""


def hub_page(podcasts_with_counts):
    cards = ""
    for niche, count in podcasts_with_counts:
        pid    = niche["id"]
        c      = COLORS[pid]
        icon   = ICONS[pid]
        cover  = niche["cover_url"]
        cards += f"""
      <a href="podcasts/{pid}/" class="card" style="--accent:{c['accent']};--text:{c['text']};">
        <img src="{cover}" alt="{niche['title']}" class="card-cover">
        <div class="card-body">
          <div class="card-icon">{icon}</div>
          <h3>{niche['title']}</h3>
          <p>{niche['description'][:100]}...</p>
          <div class="card-meta">
            <span class="ep-count">{count} episodes</span>
            <span class="daily-badge">● Daily</span>
          </div>
        </div>
      </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Podcast Network — 7 Free Podcasts, Updated Every Day</title>
  <meta name="description" content="7 free daily podcasts covering AI, finance, health, crypto, startups, world news, and true crime. 5 minutes every morning. Free forever.">
  <meta property="og:title" content="Daily Podcast Network">
  <meta property="og:description" content="7 free daily podcasts. 5 minutes every morning.">
  <meta property="og:image" content="{BASE_URL}/assets/cover.png">
  <meta property="og:url" content="{BASE_URL}/">
  <style>
    *{{ margin:0; padding:0; box-sizing:border-box; }}
    body{{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#080810; color:#fff; }}
    a{{ color:inherit; text-decoration:none; }}

    header{{
      text-align:center; padding:60px 20px 50px;
      background:linear-gradient(180deg, #0f0520 0%, #080810 100%);
      border-bottom:1px solid #ffffff10;
    }}
    header h1{{ font-size:2.8rem; font-weight:900; margin-bottom:14px;
      background:linear-gradient(135deg,#fff 0%,#a78bfa 100%);
      -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    header p{{ color:#888; font-size:1.1rem; max-width:500px; margin:0 auto 30px; line-height:1.6; }}
    .header-stats{{ display:flex; gap:32px; justify-content:center; flex-wrap:wrap; }}
    .hstat{{ text-align:center; }}
    .hstat-num{{ font-size:1.8rem; font-weight:800; color:#a78bfa; }}
    .hstat-label{{ font-size:0.8rem; color:#666; margin-top:2px; }}

    .grid{{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:24px; max-width:1100px; margin:50px auto; padding:0 24px; }}

    .card{{
      background:#0f0f1f; border:1px solid #ffffff10; border-radius:16px;
      overflow:hidden; transition:all 0.25s; display:flex; flex-direction:column;
    }}
    .card:hover{{ border-color:var(--accent); transform:translateY(-4px); box-shadow:0 16px 40px var(--accent)22; }}
    .card-cover{{ width:100%; height:180px; object-fit:cover; }}
    .card-body{{ padding:20px; flex:1; display:flex; flex-direction:column; }}
    .card-icon{{ font-size:1.6rem; margin-bottom:8px; }}
    .card-body h3{{ font-size:1.1rem; font-weight:700; margin-bottom:8px; color:#fff; }}
    .card-body p{{ font-size:0.85rem; color:#888; line-height:1.6; flex:1; }}
    .card-meta{{ display:flex; align-items:center; justify-content:space-between; margin-top:16px; }}
    .ep-count{{ font-size:0.8rem; color:#555; }}
    .daily-badge{{ font-size:0.75rem; color:var(--text); font-weight:600; }}

    footer{{ text-align:center; padding:30px; color:#333; font-size:0.8rem; border-top:1px solid #ffffff08; margin-top:40px; }}

    @media(max-width:500px){{ header h1{{ font-size:1.8rem; }} }}
  </style>
</head>
<body>

<header>
  <h1>🎙️ Daily Podcast Network</h1>
  <p>7 free daily podcasts. 5 minutes every morning.<br>AI-generated. Always fresh. Always free.</p>
  <div class="header-stats">
    <div class="hstat"><div class="hstat-num">7</div><div class="hstat-label">Podcasts</div></div>
    <div class="hstat"><div class="hstat-num">Daily</div><div class="hstat-label">New Episodes</div></div>
    <div class="hstat"><div class="hstat-num">5 min</div><div class="hstat-label">Per Episode</div></div>
    <div class="hstat"><div class="hstat-num">Free</div><div class="hstat-label">Forever</div></div>
  </div>
</header>

<div class="grid">
  {cards}
</div>

<footer>
  © 2026 Daily Podcast Network · Built with AI · Updated every morning
</footer>

</body>
</html>"""


def main():
    podcasts_with_counts = []
    for niche in PODCASTS:
        pid      = niche["id"]
        episodes = load_episodes(pid)
        podcasts_with_counts.append((niche, len(episodes)))

        out_dir = f"podcasts/{pid}"
        os.makedirs(out_dir, exist_ok=True)
        html = podcast_page(niche, episodes)
        with open(f"{out_dir}/index.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[page] podcasts/{pid}/index.html  ({len(episodes)} episodes)")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(hub_page(podcasts_with_counts))
    print("[page] index.html (hub)")


if __name__ == "__main__":
    main()
