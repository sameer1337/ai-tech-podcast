"""
Upload all podcast episodes to a single YouTube channel.
- One channel hosts all 7 niches, organised by playlists
- One refresh token (YT_REFRESH_TOKEN) in GitHub Secrets
- Playlist IDs auto-created on first run, stored in logs/yt_playlists.json
Usage: python upload_youtube.py --niche ai-tech --episode episodes/ep0001_2026-06-29.mp3
"""

import os
import re
import sys
import json
import argparse
import subprocess
import tempfile
from datetime import datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from niches import PODCAST_MAP

# ── Single channel config ──────────────────────────────────────────────────
# Set YT_CHANNEL_ID and YT_REFRESH_TOKEN in GitHub Secrets (one channel for all niches)
CHANNEL_ID    = os.environ.get("YT_CHANNEL_ID", "")
REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN", "")

GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

PLAYLIST_CACHE = "logs/yt_playlists.json"

# Niche → YouTube category ID
CATEGORY_IDS = {
    "ai-tech":    "28",  # Science & Technology
    "finance":    "25",  # News & Politics
    "health":     "26",  # Howto & Style
    "startup":    "25",  # News & Politics
    "crypto":     "28",  # Science & Technology
    "world-news": "25",  # News & Politics
    "true-crime": "25",  # News & Politics
}


def get_youtube_client(refresh_token: str = None):
    token = refresh_token or REFRESH_TOKEN
    creds = Credentials(
        token=None,
        refresh_token=token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def get_or_create_playlist(youtube, niche: dict) -> str:
    """Return playlist ID for this niche, creating it if it doesn't exist yet."""
    os.makedirs("logs", exist_ok=True)
    cache = {}
    if os.path.exists(PLAYLIST_CACHE):
        with open(PLAYLIST_CACHE) as f:
            cache = json.load(f)

    nid = niche["id"]
    if nid in cache:
        return cache[nid]

    print(f"[youtube] Creating playlist: {niche['title']}")
    resp = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title":       niche["title"],
                "description": niche["description"][:500],
            },
            "status": {"privacyStatus": "public"},
        },
    ).execute()
    playlist_id = resp["id"]
    cache[nid] = playlist_id
    with open(PLAYLIST_CACHE, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"[youtube] Playlist created: {playlist_id}")
    return playlist_id


def add_to_playlist(youtube, video_id: str, playlist_id: str):
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        },
    ).execute()


def create_video(audio_path: str, cover_path: str, out_path: str,
                 niche_id: str = "", episode_title: str = "",
                 stories: list = None, script: str = "") -> bool:
    """Create animated video: per-story cartoon images + xfade transitions + waveform + subtitles."""
    if niche_id:
        try:
            from generate_video import create_animated_video
            return create_animated_video(niche_id, audio_path, episode_title, out_path,
                                         stories=stories or [], script=script)
        except Exception as e:
            print(f"[animated video] Failed ({e}), falling back to static image")

    # Fallback: static cover + audio (original behaviour)
    try:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_bin = "ffmpeg"
    cmd = [
        ffmpeg_bin, "-y",
        "-loop", "1",
        "-i", cover_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print("[ffmpeg error]", result.stderr.decode()[-500:])
        return False
    return True


# ── Title uniqueness ────────────────────────────────────────────────────────
# Big stories lead the feeds for days, so different episodes can end up with
# the same top story and therefore the same title. Every uploaded title is
# recorded here (committed via logs/); on collision we rotate to the next
# story, or append the date as a last resort.
TITLE_REGISTRY = "logs/yt_titles.json"


def _load_used_titles() -> set:
    if os.path.exists(TITLE_REGISTRY):
        try:
            with open(TITLE_REGISTRY, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def register_title(title: str):
    titles = list(_load_used_titles())
    titles.append(title.strip().lower())
    os.makedirs("logs", exist_ok=True)
    with open(TITLE_REGISTRY, "w", encoding="utf-8") as f:
        json.dump(sorted(titles)[-3000:], f, indent=0)


def pick_unused_story(niche: dict, episode_number: int, story_list: list):
    """Return (title, rotated_stories) where the title hasn't been used before.
    Rotates the story list so the title/thumbnail/description all lead with
    the same story. Appends the date if every story's title is taken."""
    used = _load_used_titles()
    for i, story in enumerate(story_list):
        title = build_title(niche, episode_number, story)
        if title.strip().lower() not in used:
            if i > 0:
                print(f"[title] Top {i} story title(s) already used - leading with: {story[:60]}")
            return title, story_list[i:] + story_list[:i]
    base = build_title(niche, episode_number, story_list[0] if story_list else "")
    suffix = datetime.utcnow().strftime(" (%b %d)")
    title = base[: 100 - len(suffix)].rstrip() + suffix
    print(f"[title] All story titles used - date-suffixed: {title}")
    return title, story_list


def build_title(niche: dict, episode_number: int, top_story: str = "") -> str:
    """SEO title: lead with the full story hook (the part that earns the click);
    append the show name only if it still fits in YouTube's 100-char limit,
    so a long headline is never truncated mid-hook by the '| Show' suffix."""
    if top_story:
        story = top_story.encode("ascii", errors="ignore").decode("ascii").strip()
        if len(story) > 90:                       # keep more of the headline than before
            story = story[:90].rsplit(" ", 1)[0].rstrip(" ,-—:|")
        suffix = f" | {niche['title']}"
        return story + suffix if len(story) + len(suffix) <= 100 else story
    today = datetime.utcnow().strftime("%b %d, %Y")
    return f"{niche['title']} — Daily News Brief {today}"


def build_description(niche: dict, episode_number: int, script_excerpt: str = "",
                      stories: list = None) -> str:
    spotify_url = niche.get("spotify_url", "")
    today_long  = datetime.utcnow().strftime("%B %d, %Y")
    nid         = niche["id"]

    def clean(text: str, limit: int = 0) -> str:
        t = text.encode("ascii", errors="ignore").decode("ascii").strip()
        return t[:limit] if limit else t

    # ── Show intro — unique per show ─────────────────────────────────────────
    show_intro = {
        "ai-tech":
            "AI Tech Daily is your morning briefing for everything happening in artificial "
            "intelligence and technology. Every day we break down the most important AI "
            "breakthroughs, model releases, industry moves, and research in plain English — "
            "no jargon, no hype, no filler. Whether you follow OpenAI, Google DeepMind, "
            "Meta AI, or the latest open-source models, this is the fastest way to stay "
            "informed.",
        "finance":
            "Money Minute Daily cuts through the noise of global markets every morning. "
            "We cover stocks, bonds, commodities, economic data, central bank decisions, "
            "and the personal finance moves that actually matter. In under 10 minutes you "
            "get everything you need to understand where the money is moving and why.",
        "health":
            "Health Edge Daily translates the latest medical research, nutrition science, "
            "and longevity studies into clear, actionable insights. Every morning we cover "
            "new clinical findings, public health developments, and the breakthroughs that "
            "could change how you live and feel — backed by real studies, not trends.",
        "startup":
            "Startup Wire Daily tracks the funding rounds, founder pivots, product launches, "
            "and strategic acquisitions shaping the startup world. From seed stage to IPO, "
            "we keep you updated on who is building what, who is backing them, and why it "
            "matters for the future of business and technology.",
        "crypto":
            "Crypto Daily Brief is your no-nonsense morning update on Bitcoin, Ethereum, "
            "DeFi protocols, Web3 infrastructure, and the regulatory moves affecting the "
            "entire digital asset space. Whether markets are green or red, we keep you "
            "grounded in the facts that drive price and adoption.",
        "world-news":
            "Trending Now Daily explains the stories the whole internet is searching "
            "for. Every day we take Google's top trending searches and break down what "
            "actually happened and why everyone is suddenly talking about it — news, "
            "viral moments, and the answers behind the search spikes.",
        "true-crime":
            "True Crime Digest explores real criminal cases — from the investigation and "
            "arrest to the courtroom and verdict. Each episode dives into one compelling "
            "story with full context: the evidence, the timeline, the people involved, "
            "and what the outcome means for justice.",
    }.get(nid, niche["description"])

    # ── Story bullets ─────────────────────────────────────────────────────────
    story_bullets = ""
    if stories:
        bullets = "\n".join(f"  - {clean(s)}" for s in stories[:5])
        story_bullets = f"Today's stories:\n{bullets}\n"

    # ── Script excerpt ────────────────────────────────────────────────────────
    script_block = ""
    if script_excerpt:
        raw   = clean(script_excerpt)
        chunk = raw[:1500]
        last  = max(chunk.rfind(". "), chunk.rfind("! "), chunk.rfind("? "))
        if last > 600:
            chunk = chunk[:last + 1]
        script_block = f"\n{chunk}\n"

    # ── Timestamps ────────────────────────────────────────────────────────────
    ts_lines = ["00:00 Introduction"]
    if stories:
        for i, s in enumerate(stories[:5]):
            ts_lines.append(f"0{i+1}:00 {clean(s, 65)}")
    ts_lines.append(f"0{len(ts_lines)}:30 Outro")
    timestamps = "\n".join(ts_lines)

    # ── Blog section — topic-aware ────────────────────────────────────────────
    SITE_BASE = "https://daily.mapt.cloud"
    slug_map  = {
        "ai-tech": "ai-tech", "finance": "finance", "health": "health",
        "startup": "startup", "crypto": "crypto",
        "world-news": "world", "true-crime": "truecrime",
    }
    blog_url = f"{SITE_BASE}/{slug_map.get(nid, nid)}"

    blog_teaser = {
        "ai-tech":
            "Prefer reading? Every episode has a full written article on our blog — "
            "with source links, key quotes, and deeper context on today's AI and tech stories.",
        "finance":
            "Prefer reading? Every episode has a full written article with data, charts, "
            "and source links covering today's market and finance stories.",
        "health":
            "Prefer reading? Every episode has a full written article with study references, "
            "expert quotes, and practical takeaways from today's health research.",
        "startup":
            "Prefer reading? Every episode has a full written article with funding details, "
            "founder backgrounds, and source links from today's startup stories.",
        "crypto":
            "Prefer reading? Every episode has a full written article with price context, "
            "on-chain data, and source links from today's crypto and Web3 stories.",
        "world-news":
            "Prefer reading? Every episode has a full written article explaining each "
            "trending story with background and source links.",
        "true-crime":
            "Prefer reading? Every episode has a full written article with case timeline, "
            "court documents, and source links for today's true crime story.",
    }.get(nid, "Prefer reading? Every episode has a full written article with source links and analysis.")

    # ── Vita section — relevant to health show, generic plug elsewhere ────────
    vita_section = ""
    if nid == "health":
        vita_section = (
            "\n----------------------------------------\n"
            "TRACK YOUR HEALTH WITH VITA\n"
            "----------------------------------------\n"
            "Vita is a free AI-powered wellness app that helps you track nutrition, "
            "sleep, fitness, and mental wellbeing in one place. Built for people who "
            "take their health seriously.\n"
            "Try Vita free: https://mapt.cloud/vita\n"
        )

    # ── Mapt agency section ───────────────────────────────────────────────────
    mapt_section = (
        "\n----------------------------------------\n"
        "BUILT BY MAPT\n"
        "----------------------------------------\n"
        "Velox Daily is produced by Mapt — a digital agency helping businesses grow "
        "through content, automation, and AI-powered marketing. If you want a podcast, "
        "blog, or content system like this built for your brand, visit us at mapt.cloud\n"
        "Website: https://mapt.cloud\n"
    )

    # ── Hashtags ──────────────────────────────────────────────────────────────
    show_tag = niche["title"].replace(" ", "")
    hashtags = {
        "ai-tech":    "#AI #ArtificialIntelligence #MachineLearning #OpenAI #ChatGPT #TechNews #AINews",
        "finance":    "#Finance #Investing #StockMarket #PersonalFinance #Economy #WallStreet #MoneyNews",
        "health":     "#Health #Wellness #Longevity #Nutrition #MedicalResearch #HealthNews #Fitness",
        "startup":    "#Startup #VentureCapital #Founders #BusinessNews #Innovation #Entrepreneurship",
        "crypto":     "#Crypto #Bitcoin #Ethereum #DeFi #Web3 #Blockchain #CryptoNews #BTC",
        "world-news": "#Trending #TrendingNow #ViralNews #GoogleTrends #WhyIsItTrending #BreakingNews",
        "true-crime": "#TrueCrime #CrimePodcast #MurderMystery #CriminalInvestigation #Justice #CrimeNews",
    }.get(nid, "#Podcast #DailyNews")

    return (
        f"{today_long} | {niche['title']} - Episode {episode_number}\n\n"
        f"{show_intro}\n\n"
        f"{story_bullets}\n"
        f"{script_block}"
        f"\n----------------------------------------\n"
        f"TIMESTAMPS\n"
        f"----------------------------------------\n"
        f"{timestamps}\n"
        f"\n----------------------------------------\n"
        f"READ THE FULL ARTICLE\n"
        f"----------------------------------------\n"
        f"{blog_teaser}\n"
        f"Today's article: {blog_url}\n"
        f"All daily briefings: {SITE_BASE}\n"
        f"\n----------------------------------------\n"
        f"LISTEN FREE ON ALL PLATFORMS\n"
        f"----------------------------------------\n"
        f"Spotify      : {spotify_url}\n"
        f"Apple Podcasts, Amazon Music, Pocket Casts\n"
        f"Search       : \"{niche['title']}\" on any podcast app\n\n"
        f"New episode every single day. Subscribe and never miss one.\n"
        f"{vita_section}"
        f"{mapt_section}"
        f"\n----------------------------------------\n"
        f"{hashtags} #{show_tag} #DailyPodcast #FreePodcast #VeloxDaily\n"
    )


def _load_font(size: int):
    """Bold TTF that exists on both Windows (local) and Ubuntu (CI)."""
    from PIL import ImageFont
    for p in ("C:/Windows/Fonts/arialbd.ttf",
              "C:/Windows/Fonts/ARIALBD.TTF",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _thumb_hook(top_story: str, niche_id: str) -> str:
    """A punchy 2-4 word ALL-CAPS thumbnail hook from the story (Groq, with a
    plain-extraction fallback). Text on the thumbnail is the #1 CTR lever."""
    try:
        from groq import Groq
        from config import GROQ_API_KEY, GROQ_MODEL
        r = Groq(api_key=GROQ_API_KEY).chat.completions.create(
            model=GROQ_MODEL, max_tokens=30, temperature=0.7,
            messages=[{"role": "user", "content":
                "Write a 2 to 4 word ALL-CAPS thumbnail hook that creates curiosity "
                "for this news headline. Punchy but ACCURATE — do NOT exaggerate or "
                "claim anything the headline does not actually say (no 'COLLAPSE', "
                "'BANNED', 'DEAD' unless the headline states it). No punctuation, no "
                "quotes, no hashtags, just the words.\nHeadline: " + top_story[:160]}])
        hook = r.choices[0].message.content.strip().strip('"').upper()
        hook = re.sub(r"[^A-Z0-9 &%$]", "", hook).strip()
        words = hook.split()
        if 1 <= len(words) <= 5 and len(hook) <= 26:
            return " ".join(words)
    except Exception as e:
        print(f"[thumbnail] hook gen failed ({e}) - using extraction")
    stop = {"the","a","an","of","to","in","on","for","and","as","is","are",
            "with","by","from","its","after","over","amid","says","will"}
    words = [w for w in re.sub(r"[^A-Za-z0-9 ]", " ", top_story).split()
             if w.lower() not in stop]
    return " ".join(words[:3]).upper() or "TODAY'S TOP STORY"


def _wrap(draw, text: str, font, max_w: int) -> list:
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = word
    if cur:
        lines.append(cur)
    return lines


def _overlay_hook(path: str, hook: str, accent: str = "#FFE000"):
    """Burn a bold, wrapped, high-contrast hook onto the lower area of the
    thumbnail with a dark scrim + heavy stroke so it reads at phone size."""
    from PIL import Image, ImageDraw
    img = Image.open(path).convert("RGB")
    W, H = img.size
    draw = ImageDraw.Draw(img, "RGBA")

    # Shrink font until the hook fits in <=2 lines within the safe width.
    max_w = int(W * 0.90)
    size = 168
    while size > 70:
        font = _load_font(size)
        lines = _wrap(draw, hook, font, max_w)
        if len(lines) <= 2 and max((draw.textlength(l, font=font) for l in lines), default=0) <= max_w:
            break
        size -= 8
    line_h = size + 14
    block_h = line_h * len(lines)
    y0 = int(H * 0.97) - block_h            # sit near the bottom

    # Dark scrim behind the text for legibility on any background.
    draw.rectangle([0, y0 - 24, W, H], fill=(0, 0, 0, 150))
    for i, ln in enumerate(lines):
        w = draw.textlength(ln, font=font)
        x = (W - w) / 2
        y = y0 + i * line_h
        draw.text((x, y), ln, font=font, fill=accent,
                  stroke_width=max(6, size // 16), stroke_fill=(0, 0, 0))
    img.save(path, "JPEG", quality=90)
    print(f"[thumbnail] overlaid hook: '{hook}' ({size}px, {len(lines)} line(s))")


def generate_thumbnail(niche_id: str, top_story: str, out_path: str) -> bool:
    """Generate a unique 1280x720 thumbnail from Pollinations for this episode,
    then burn on a bold text hook (Pollinations art alone = no CTR hook)."""
    import urllib.request, urllib.parse, time
    THUMB_STYLE = {
        "ai-tech":    "bold tech magazine cover style, glowing AI circuit brain, deep blue purple, dramatic lighting",
        "finance":    "bold financial magazine cover, stock chart arrows, gold coins, dark navy background",
        "health":     "clean health magazine cover, medical symbols, bright green white, modern minimal",
        "startup":    "startup pitch deck style, rocket launch, bold typography space, deep purple orange",
        "crypto":     "crypto news thumbnail, bitcoin logo glow, neon cyan black, cyberpunk dramatic",
        "world-news": "viral trending story thumbnail, fire gradient red orange, upward graph arrow, urgent energetic look",
        "true-crime": "true crime documentary thumbnail, dark shadowy, red spotlight, crime scene tape",
    }
    # Accent colour per niche for the burned-on text hook.
    THUMB_ACCENT = {
        "ai-tech": "#3AD1FF", "finance": "#FFD700", "health": "#8CFF6B",
        "startup": "#FF8A3D", "crypto": "#2BE6C8", "world-news": "#FFE000",
        "true-crime": "#FF4040",
    }
    style = THUMB_STYLE.get(niche_id, "bold news thumbnail, dramatic lighting, vibrant colors")
    topic = top_story[:80].encode("ascii", errors="ignore").decode("ascii")
    # Keep the AI art clean (no garbled AI text) — we burn crisp real text on top.
    prompt = (f"{style}, topic: {topic}, absolutely no text no letters no numbers no captions, "
              "empty lower third, cinematic composition, high contrast")
    encoded = urllib.parse.quote(prompt)
    seed = abs(hash(top_story + niche_id)) % 99999
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&nologo=true&model=flux&seed={seed}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "podcast-bot/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 5000:
                raise ValueError("Image too small")
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"[thumbnail] Generated ({len(data)//1024}KB)")
            try:
                hook = _thumb_hook(top_story, niche_id)
                _overlay_hook(out_path, hook, THUMB_ACCENT.get(niche_id, "#FFE000"))
            except Exception as e:
                print(f"[thumbnail] text overlay failed ({e}) - using plain art")
            return True
        except Exception as e:
            print(f"[thumbnail] Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(8)
    return False


def upload_thumbnail(youtube, video_id: str, thumb_path: str):
    """Upload custom thumbnail to YouTube video."""
    from googleapiclient.http import MediaFileUpload as MFU
    media = MFU(thumb_path, mimetype="image/jpeg")
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
    print(f"[thumbnail] Uploaded to video {video_id}")


NICHE_TAGS = {
    "ai-tech": [
        "AI news", "artificial intelligence", "machine learning", "OpenAI", "ChatGPT",
        "tech news", "AI podcast", "daily AI", "deep learning", "AI today",
        "AI Tech Daily", "Velox Daily", "tech podcast", "AI 2026", "LLM news",
    ],
    "finance": [
        "finance news", "stock market", "investing", "personal finance", "economy",
        "Wall Street", "daily finance", "money podcast", "stock news", "financial news",
        "Money Minute Daily", "Velox Daily", "market news", "investing tips", "economy 2026",
    ],
    "health": [
        "health news", "wellness", "longevity", "nutrition", "medical news",
        "fitness", "health podcast", "daily health", "science health", "mental health",
        "Health Edge Daily", "Velox Daily", "health tips", "medical research", "diet news",
    ],
    "startup": [
        "startup news", "venture capital", "founders", "business news", "innovation",
        "entrepreneurship", "funding rounds", "tech startups", "startup podcast", "VC news",
        "Startup Wire Daily", "Velox Daily", "startup 2026", "business podcast", "product launch",
    ],
    "crypto": [
        "crypto news", "bitcoin", "ethereum", "DeFi", "Web3", "blockchain",
        "cryptocurrency", "BTC price", "crypto podcast", "crypto today",
        "Crypto Daily Brief", "Velox Daily", "crypto 2026", "altcoin news", "NFT news",
    ],
    "world-news": [
        "trending", "trending now", "trending today", "viral news", "google trends",
        "why is it trending", "breaking news", "news today", "viral moments", "explained",
        "Trending Now Daily", "Velox Daily", "trending 2026", "internet news", "top searches",
    ],
    "true-crime": [
        "true crime", "crime podcast", "murder mystery", "investigation", "justice",
        "criminal cases", "court drama", "true crime daily", "crime news", "unsolved crimes",
        "True Crime Digest", "Velox Daily", "crime 2026", "criminal investigation", "cold case",
    ],
}


def build_tags(niche_id: str, stories: list = None) -> list:
    base = NICHE_TAGS.get(niche_id, ["podcast", "daily news", "Velox Daily"])
    extra = []
    if stories:
        for s in stories[:3]:
            words = s.encode("ascii", errors="ignore").decode("ascii").split()
            kw = " ".join(words[:4])
            if kw and kw not in base:
                extra.append(kw)
    return (base + extra)[:30]


def upload_to_youtube(youtube, video_path: str, title: str, description: str,
                      category_id: str = "25", tags: list = None):
    import time as _time
    print(f"[youtube] Uploading: {title}")
    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "categoryId":  category_id,
            "tags":        tags or ["podcast", "daily news", "Velox Daily"],
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024*5)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    retry = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"[youtube] Upload {pct}%", end="\r")
                retry = 0  # reset on progress
        except Exception as e:
            msg = str(e)
            if any(k in msg for k in ("quotaExceeded", "rateLimitExceeded", "uploadLimitExceeded", "Quota exceeded")):
                print(f"\n[youtube] Upload rejected by quota/rate limit — aborting. Raw error:\n{msg}")
                sys.exit(3)
            retry += 1
            if retry > 5:
                raise
            wait = min(2 ** retry, 60)
            print(f"\n[youtube] Network error ({e.__class__.__name__}), retry {retry}/5 in {wait}s...")
            _time.sleep(wait)

    print(f"\n[youtube] Done -> https://youtu.be/{response['id']}")
    return response["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche",   required=True, help="Niche ID e.g. ai-tech")
    parser.add_argument("--episode", required=True, help="Path to MP3 file")
    parser.add_argument("--number",  type=int, default=1, help="Episode number")
    parser.add_argument("--excerpt", default="", help="Script excerpt for description")
    parser.add_argument("--stories",     default="", help="Story headlines separated by ||")
    parser.add_argument("--script-file", default="", help="Path to script .txt file for subtitles")
    args = parser.parse_args()

    niche = PODCAST_MAP.get(args.niche)
    if not niche:
        print(f"[error] Unknown niche: {args.niche}")
        sys.exit(1)

    if not REFRESH_TOKEN:
        print(f"[skip] YT_REFRESH_TOKEN not set — skipping YouTube upload")
        sys.exit(0)

    cover_map = {
        "ai-tech":    "assets/cover.png",
        "finance":    "assets/cover_finance.png",
        "health":     "assets/cover_health.png",
        "startup":    "assets/cover_startup.png",
        "crypto":     "assets/cover_crypto.png",
        "world-news": "assets/cover_trending.png",
        "true-crime": "assets/cover_truecrime.png",
    }
    cover_path = cover_map.get(args.niche, "assets/cover.png")

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "episode.mp4")
        print(f"[video] Building animated video for {args.niche}...")
        story_list = [s.strip() for s in args.stories.split("||") if s.strip()] if args.stories else []

        # Pick a lead story whose title hasn't been used on the channel yet;
        # rotate the list so video scenes, thumbnail and description match it
        if story_list:
            title, story_list = pick_unused_story(niche, args.number, story_list)
        else:
            title = args.excerpt[:80] if args.excerpt else build_title(niche, args.number)

        ep_title   = args.excerpt[:80] if args.excerpt else title
        script_text = ""
        if args.script_file and os.path.exists(args.script_file):
            with open(args.script_file, encoding="utf-8") as f:
                script_text = f.read()
        if not create_video(args.episode, cover_path, video_path,
                            niche_id=args.niche, episode_title=ep_title,
                            stories=story_list, script=script_text):
            print("[error] Video creation failed")
            sys.exit(1)

        youtube     = get_youtube_client()
        top_story   = story_list[0] if story_list else args.excerpt
        desc        = build_description(niche, args.number, args.excerpt, story_list)
        category_id = CATEGORY_IDS.get(args.niche, "25")
        tags        = build_tags(args.niche, story_list)
        print(f"[tags] {tags[:5]}... ({len(tags)} total)")
        video_id    = upload_to_youtube(youtube, video_path, title, desc, category_id, tags)
        register_title(title)

        # Upload unique thumbnail
        thumb_path = os.path.join(tmpdir, "thumbnail.jpg")
        print(f"[thumbnail] Generating for: {top_story[:60]}")
        if generate_thumbnail(args.niche, top_story, thumb_path):
            try:
                upload_thumbnail(youtube, video_id, thumb_path)
                print(f"[thumbnail] Done")
            except Exception as e:
                print(f"[thumbnail] Upload failed: {e}")
        else:
            print(f"[thumbnail] Generation failed - video will use default thumbnail")

        # Add to niche playlist (creates it if missing)
        try:
            playlist_id = get_or_create_playlist(youtube, niche)
            add_to_playlist(youtube, video_id, playlist_id)
            print(f"[youtube] Added to playlist: {playlist_id}")
        except Exception as e:
            print(f"[youtube] Playlist step failed (non-fatal): {e}")

        # Save video ID for website embedding
        import datetime as _dt
        today = _dt.datetime.utcnow().strftime("%Y-%m-%d")
        log_dir = f"logs/{args.niche}"
        os.makedirs(log_dir, exist_ok=True)
        with open(f"{log_dir}/{today}_youtube.txt", "w") as f:
            f.write(video_id)

    print(f"[done] https://youtu.be/{video_id}")


if __name__ == "__main__":
    main()
