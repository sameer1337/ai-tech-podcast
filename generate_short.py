"""
Generate a 30-45s vertical YouTube Short from today's episode.

Pipeline:
  1. Groq picks the single most gripping story from today's episode and writes
     a hook-first ~80-word Shorts script (loop-back ending, no wind-up).
  2. Edge TTS synthesizes the voiceover, capturing per-word timings
     (WordBoundary events) for accurately timed burned-in captions.
  3. Pollinations generates one 1080x1920 background image for the story.
  4. FFmpeg renders: slow Ken Burns zoom + big centered word-chunk captions
     (kept inside the Shorts safe zone - top 20% / bottom 25% are YouTube UI)
     + a "Full story" CTA in the final seconds.

Output:
  shorts/<niche>_<date>.mp4
  logs/<niche>/<date>_short.json   (title, caption, script - reused by uploader
                                    and ready-made as a TikTok/Reels caption)

Usage:
  python generate_short.py --niche startup [--date 2026-07-09]
"""

import os
import sys
import json
import re
import math
import asyncio
import argparse
import subprocess
import tempfile
import urllib.request
import urllib.parse
import time
from datetime import datetime

from niches import PODCAST_MAP
from generate_video import get_ffmpeg, get_audio_duration, FALLBACK_COVERS

SHORT_RATE = "+12%"   # slightly faster than episodes - Shorts pacing

# YouTube policy/advertiser red flags - these words in a TITLE or on-screen
# hook get Shorts age-restricted, demonetized, or removed (spoken script and
# episode content are judged more leniently than packaging).
_SENSITIVE = re.compile(
    r"self.?harm|suicide|rape[sd]?|incest|pedophil|child\s+(?:sex|abuse|porn)"
    r"|behead(?:ed|ing)?|dismember\w*|molest\w*",
    re.IGNORECASE,
)
_SAFE_SWAPS = [
    (re.compile(r"self.?harm", re.I),            "tragedy"),
    (re.compile(r"suicide", re.I),               "tragedy"),
    (re.compile(r"rape[sd]?", re.I),             "assault"),
    (re.compile(r"behead(?:ed|ing)?", re.I),     "killing"),
    (re.compile(r"dismember\w*", re.I),          "gruesome act"),
    (re.compile(r"molest\w*|pedophil\w*", re.I), "abuse"),
    (re.compile(r"incest", re.I),                "family abuse"),
    (re.compile(r"child\s+(?:sex|abuse|porn)\w*", re.I), "crimes against a child"),
]


def _sanitize_packaging(data: dict) -> dict:
    """Soften policy-flagged words in title/overlay (packaging only)."""
    for key in ("title", "overlay"):
        text = data.get(key, "")
        if text and _SENSITIVE.search(text):
            for pat, repl in _SAFE_SWAPS:
                text = pat.sub(repl, text)
            print(f"[safety] Softened {key}: {data[key][:50]} -> {text[:50]}")
            data[key] = text
    return data

# Per-niche vertical background style (distinct from the 16:9 episode style)
SHORT_STYLE = {
    "ai-tech":    "dramatic vertical poster, glowing AI circuitry, deep blue purple neon, cinematic",
    "finance":    "dramatic vertical poster, stock chart skyline, gold on dark navy, cinematic",
    "health":     "dramatic vertical poster, human silhouette with glowing anatomy, teal on dark, cinematic",
    "startup":    "dramatic vertical poster, rocket launch over city, warm orange purple, cinematic",
    "crypto":     "dramatic vertical poster, bitcoin neon glow, cyan black cyberpunk, cinematic",
    "world-news": "dramatic vertical poster, viral trending story, fiery red orange, upward arrow energy, cinematic",
    "true-crime": "dramatic vertical poster, noir crime scene, red spotlight in darkness, moody fog, cinematic",
    "worldcup":   "dramatic vertical poster, packed soccer stadium under floodlights, world cup trophy glow, green pitch, confetti, cinematic",
    "football":   "dramatic vertical poster, floodlit soccer stadium at night, green pitch, roaring crowd, motion blur action, cinematic sports poster",
    "combat":     "dramatic vertical poster, boxing ring under harsh spotlights, two silhouetted fighters, sweat and motion blur, intense crowd, cinematic fight poster",
}

# ── Event topics: time-boxed Shorts with no podcast episode behind them ───────
# Stories come from Google News search; CTA funnels to an existing show.
# After end_date the topic silently skips - no cleanup needed.
TOPICS = {
    "worldcup": {
        "title":     "World Cup 2026",
        "query":     "FIFA World Cup 2026",
        "voice":     "en-GB-RyanNeural",
        "cta_show":  "Trending Now Daily",     # funnel target (covers WC trends)
        "end_date":  "2026-07-20",             # day after the July 19 final
        "category":  "17",                     # YouTube: Sports
        "hashtags":  "#Shorts #WorldCup #FIFAWorldCup #WorldCup2026 #Soccer #Football",
        "tags":      ["world cup", "world cup 2026", "FIFA world cup", "soccer",
                      "football", "world cup today", "Velox Daily", "shorts"],
    },
    # Evergreen football lane — replaces worldcup after the July 19 final so the
    # channel never goes dark. "query" is a LIST: create_topic_short rotates by
    # day-of-year, so the Short stays fresh AND every term is unambiguously SOCCER
    # (bare "football" in US Google News returns NFL, so we never use it alone).
    "football": {
        "title":     "Football Daily",
        "query":     ["Premier League", "Champions League", "La Liga football",
                      "Lionel Messi", "Cristiano Ronaldo", "UEFA football",
                      "football transfer news", "Serie A football",
                      "Bundesliga football", "soccer match result"],
        "voice":     "en-GB-RyanNeural",
        "cta_show":  "Trending Now Daily",
        "end_date":  "2035-01-01",             # evergreen
        "category":  "17",                     # YouTube: Sports
        "blurb":     "Daily football news in under a minute.",
        "hashtags":  "#Shorts #Football #Soccer #PremierLeague #ChampionsLeague #Futbol",
        "tags":      ["football", "soccer", "premier league", "champions league",
                      "football news", "football shorts", "Velox Daily", "shorts"],
    },
    # Combat-sports test lane — knockouts/fights are a proven faceless-Shorts
    # goldmine (one 22s KO short = 1.4M views), same "shocking moment" DNA as the
    # true-crime + football-drama winners. Evergreen rotating query.
    "combat": {
        "title":     "Combat Daily",
        "query":     ["UFC", "boxing knockout", "MMA fight", "UFC results",
                      "boxing fight", "UFC knockout", "heavyweight boxing",
                      "MMA knockout", "boxing news", "UFC news"],
        "voice":     "en-US-GuyNeural",
        "cta_show":  "Trending Now Daily",
        "end_date":  "2035-01-01",             # evergreen
        "category":  "17",                     # YouTube: Sports
        "blurb":     "Daily combat sports news in under a minute.",
        "hashtags":  "#Shorts #UFC #Boxing #MMA #Knockout #CombatSports",
        "tags":      ["ufc", "boxing", "mma", "knockout", "combat sports",
                      "fight", "Velox Daily", "shorts"],
    },
}


# -- 1. Script ----------------------------------------------------------------

def write_short_script(niche: dict, stories: list, episode_script: str) -> dict:
    """Ask Groq for a hook-first Shorts script. Falls back to trimming the episode."""
    try:
        from groq import Groq
        from config import GROQ_API_KEY, GROQ_MODEL
        client = Groq(api_key=GROQ_API_KEY)

        stories_block = "\n".join(f"- {s}" for s in stories[:5])

        # If a story matches what people are Googling today, feature THAT one
        trend_hint = ""
        try:
            from trends import fetch_trending, trend_boost
            trending = fetch_trending()
            for s in stories[:5]:
                tb, q = trend_boost(s, "", trending)
                if tb:
                    trend_hint = (f"\nIMPORTANT: the story matching '{q}' is "
                                  f"TRENDING on Google search right now - pick it "
                                  f"unless another story is dramatically stronger.\n")
                    break
        except Exception:
            pass

        # Call 1 (JSON): pick the story + packaging
        pick_prompt = f"""Today's "{niche['title']}" episode covered these stories:
{stories_block}
{trend_hint}
Pick the ONE story with the most surprising specific fact (a number, a name,
a twist) for a 35-second vertical video Short. Return ONLY JSON:
- "story": the chosen headline, verbatim from the list
- "overlay": on-screen text hook for frame 1, max 6 punchy words, no period
- "title": YouTube title, max 80 chars, curiosity-first, no clickbait lies
- "image_prompt": 10-15 words describing one dramatic scene for this story

"title" and "overlay" must be advertiser-safe: NEVER use words like suicide,
self-harm, rape, or graphic violence terms in them (imply, don't state)."""
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": pick_prompt}],
            temperature=0.7,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        if not data.get("story") or not data.get("title"):
            raise ValueError("story pick missing keys")

        # Call 2 (plain text): the voiceover - JSON mode makes llama terse,
        # plain text gets natural prose at the right length
        vo_prompt = f"""Write the spoken voiceover for a 35-second vertical news Short about this story:

{data['story']}

Facts (from today's "{niche['title']}" episode - use these, don't invent):
{episode_script[:2500]}

Rules:
- 80 to 100 words total, natural spoken prose, complete sentences.
- FIRST sentence is the hook: max 12 words, must contain the single most
  surprising specific fact. No wind-up, no "imagine", no "welcome",
  no scene-setting. Start mid-action.
- Escalate quickly: why it matters, then the strongest details.
- LAST sentence: a short open question or cliff line that makes the first
  sentence hit differently when the video loops.
- Output ONLY the spoken words. No hashtags, emoji, headings, or quotes."""

        messages = [{"role": "user", "content": vo_prompt}]
        for attempt in range(3):
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.8,
                max_tokens=400,
            )
            script = resp.choices[0].message.content.strip().strip('"')
            wc = len(script.split())
            if 65 <= wc <= 140:
                data["script"] = script
                print(f"[short] Groq script OK ({wc} words): {data['title'][:60]}")
                return data
            print(f"[short] Script {wc} words - asking for a rewrite ({attempt+1})")
            messages.append({"role": "assistant", "content": script})
            messages.append({"role": "user", "content":
                f"That was {wc} words. Rewrite it at 80-100 words, same rules. "
                "Output only the spoken words."})
        raise ValueError("script wrong length after 3 attempts")
    except Exception as e:
        print(f"[short] Groq failed ({e}) - falling back to episode opening")

    # Fallback 1: first sentences of the episode prose, capped ~85 words.
    sents = re.split(r"(?<=[.!?])\s+", episode_script.strip())
    script, words = [], 0
    for s in sents:
        s = s.strip()
        if not s:
            continue
        # only stop once we already have something - a single long first
        # chunk must not leave the script empty
        if script and words + len(s.split()) > 100:
            break
        script.append(s)
        words += len(s.split())
    script_text = " ".join(script).strip()

    # Fallback 2 (event topics like worldcup): there's no prose episode - the
    # text above is a raw "- headline: summary" bullet dump (TTS would read the
    # dashes and colons aloud) or empty. Rebuild clean spoken lines from the
    # headlines so a Groq outage degrades quality but never kills the Short
    # (empty script -> 0 TTS words -> generation fails).
    looks_bulleted = episode_script.lstrip().startswith("-")
    if stories and (looks_bulleted or len(script_text.split()) < 20):
        bits = []
        for s in stories[:4]:
            # drop only a trailing " - Publisher" / " | Publisher" tail;
            # the spaces around the separator keep scorelines like "2-1" intact
            s = re.sub(r"\s+[-|]\s+[^-|]+$", "", s).strip()
            if not s:
                continue
            bits.append(s if s.endswith((".", "!", "?")) else s + ".")
            if len(" ".join(bits).split()) >= 55:
                break
        if bits:
            script_text = "Here are today's biggest stories. " + " ".join(bits)

    top = stories[0] if stories else niche["title"]
    return {
        "story":        top,
        "overlay":      " ".join(top.split()[:6]),
        "script":       script_text,
        "title":        top[:80],
        "image_prompt": top[:90],
    }


# -- 2. TTS with word timings ---------------------------------------------------

async def _tts_stream(text: str, voice: str, mp3_path: str):
    """Synthesize and capture boundary events (offsets in 100ns ticks).
    edge-tts 7.x needs boundary="WordBoundary" (defaults to sentences);
    6.x emits WordBoundary by default and lacks the kwarg."""
    import edge_tts
    try:
        communicate = edge_tts.Communicate(text, voice, rate=SHORT_RATE,
                                           boundary="WordBoundary")
    except TypeError:
        communicate = edge_tts.Communicate(text, voice, rate=SHORT_RATE)
    words = []
    with open(mp3_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                start = chunk["offset"] / 1e7
                dur = chunk["duration"] / 1e7
                toks = chunk["text"].split()
                if len(toks) <= 1:
                    words.append((start, start + dur, chunk["text"]))
                else:
                    # Sentence event: split its span across words by char share
                    total = sum(len(t) for t in toks) or 1
                    t = start
                    for tok in toks:
                        span = dur * len(tok) / total
                        words.append((t, t + span, tok))
                        t += span
    return words


def synthesize(text: str, voice: str, mp3_path: str) -> list:
    words = asyncio.run(_tts_stream(text, voice, mp3_path))
    print(f"[short] TTS done - {len(words)} words, audio {mp3_path}")
    return words


# -- 3. Captions (ASS, safe zone) -----------------------------------------------

def _ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(words: list, duration: float, show_title: str, ass_path: str,
              overlay: str = ""):
    """Word-chunk captions centered in the safe zone + end CTA.
    Safe zone: top ~20% and bottom ~25% of a Short are covered by YouTube UI,
    so everything sits in the middle third (y ~700-1400 of 1920)."""
    # Group words into chunks of <=3 (new chunk on pauses > 0.6s)
    chunks = []
    cur = []
    for (start, end, text) in words:
        if cur and (len(cur) >= 3 or start - cur[-1][1] > 0.6):
            chunks.append(cur)
            cur = []
        cur.append((start, end, text))
    if cur:
        chunks.append(cur)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H88000000,-1,0,0,0,100,100,1,0,1,7,2,5,60,60,0,1
Style: CTA,Arial,52,&H0000E5FF,&H00FFFFFF,&H00000000,&H88000000,-1,0,0,0,100,100,1,0,1,4,1,5,60,60,0,1
Style: Hook,Arial,72,&H0000E5FF,&H00FFFFFF,&H00000000,&H88000000,-1,0,0,0,100,100,1,0,1,5,2,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for i, chunk in enumerate(chunks):
        start = chunk[0][0]
        # Hold each caption until the next chunk starts (no flicker gaps)
        end = chunks[i + 1][0][0] if i + 1 < len(chunks) else min(chunk[-1][1] + 0.4, duration)
        text = " ".join(w[2] for w in chunk).upper()
        text = text.replace("\\", "").replace("{", "").replace("}", "")
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Cap,,0,0,0,,"
            f"{{\\an5\\pos(540,960)\\fad(60,0)}}{text}"
        )

    # Pinned hook for the first ~2.5s (top of the safe zone) - YouTube grabs
    # an early frame for the Shorts-tab cover, and without this it shows a
    # meaningless mid-sentence caption fragment instead of a hook
    if overlay:
        text = overlay.upper().replace("\\", "").replace("{", "").replace("}", "")
        lines.append(
            f"Dialogue: 1,{_ass_time(0)},{_ass_time(min(2.5, duration))},Hook,,0,0,0,,"
            f"{{\\an5\\pos(540,700)\\fad(0,150)}}{text}"
        )

    # CTA during the last 3s - lower-center but still inside the safe zone
    cta_start = max(0.0, duration - 3.0)
    lines.append(
        f"Dialogue: 1,{_ass_time(cta_start)},{_ass_time(duration)},CTA,,0,0,0,,"
        f"{{\\an5\\pos(540,1330)\\fad(200,0)}}Full story: {show_title} (free on all podcast apps)"
    )

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")
    print(f"[short] Captions: {len(chunks)} chunks + CTA")


# -- 4. Background image ---------------------------------------------------------

def fetch_vertical_image(niche_id: str, image_prompt: str, out_path: str) -> bool:
    style = SHORT_STYLE.get(niche_id, "dramatic vertical poster, cinematic lighting")
    topic = image_prompt[:100].encode("ascii", errors="ignore").decode("ascii")
    prompt = f"{style}, scene: {topic}, no text, no words, no captions, vertical composition"
    seed = abs(hash(image_prompt + niche_id)) % 99999
    url = (
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
        f"?width=1080&height=1920&nologo=true&model=flux&seed={seed}"
    )
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "podcast-bot/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 5000:
                raise ValueError(f"too small ({len(data)} bytes)")
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"[short] Background image {len(data)//1024}KB")
            return True
        except Exception as e:
            print(f"[short] image attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(8)
    return False


# -- 5. Render --------------------------------------------------------------------

def render_short(image_path: str, audio_path: str, ass_path: str, out_path: str) -> bool:
    duration = get_audio_duration(audio_path)
    frames = math.ceil(duration * 30) + 15
    ffmpeg = get_ffmpeg()

    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    fc = (
        # Cover-crop to vertical, oversample, then slow Ken Burns zoom
        "[0:v]scale=1620:2880:force_original_aspect_ratio=increase,"
        "crop=1620:2880,"
        f"zoompan=z='min(zoom+0.0005,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1080x1920:fps=30,format=yuv420p[bg];"
        f"[bg]subtitles='{ass_escaped}'[v]"
    )
    cmd = [
        ffmpeg, "-y",
        "-i", image_path,
        "-i", audio_path,
        "-filter_complex", fc,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "160k",
        "-t", f"{duration:.2f}",
        "-shortest",
        out_path,
    ]
    print(f"[short] Rendering {duration:.0f}s vertical video...")
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print("[ffmpeg error]", result.stderr.decode(errors="replace")[-1200:])
        return False
    return True


# -- Main ---------------------------------------------------------------------------

def create_short(niche_id: str, date: str) -> bool:
    niche = PODCAST_MAP.get(niche_id)
    if not niche:
        print(f"[error] Unknown niche: {niche_id}")
        return False

    stories_file = f"logs/{niche_id}/{date}_stories.txt"
    script_file = f"logs/{niche_id}/{date}_script.txt"
    if not os.path.exists(script_file):
        print(f"[skip] No episode script for {niche_id} on {date}")
        return False
    with open(script_file, encoding="utf-8") as f:
        episode_script = f.read()
    stories = []
    if os.path.exists(stories_file):
        with open(stories_file, encoding="utf-8") as f:
            stories = [s.strip() for s in f.read().split("||") if s.strip()]

    data = _sanitize_packaging(write_short_script(niche, stories, episode_script))

    os.makedirs("shorts", exist_ok=True)
    out_path = f"shorts/{niche_id}_{date}.mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        mp3 = os.path.join(tmpdir, "voice.mp3")
        words = synthesize(data["script"], niche["voice"], mp3)
        if not words:
            print("[error] TTS produced no word timings")
            return False
        duration = get_audio_duration(mp3)
        if duration > 175:
            print(f"[warn] Short is {duration:.0f}s - too long, but uploading anyway")

        ass = os.path.join(tmpdir, "caps.ass")
        build_ass(words, duration, niche["title"], ass, overlay=data.get("overlay", ""))

        img = os.path.join(tmpdir, "bg.jpg")
        if not fetch_vertical_image(niche_id, data.get("image_prompt", data["story"]), img):
            # Fallback: portrait-crop the show cover
            img = FALLBACK_COVERS.get(niche_id, "assets/cover.png")
            print(f"[short] Using cover fallback: {img}")

        if not render_short(img, mp3, ass, out_path):
            return False

    # Metadata for the uploader + ready-made TikTok/Reels caption
    meta = {
        "niche":    niche_id,
        "date":     date,
        "story":    data["story"],
        "title":    data["title"],
        "overlay":  data.get("overlay", ""),
        "script":   data["script"],
        "duration": round(get_audio_duration(out_path), 1),
        "video":    out_path,
        "tiktok_caption": f"{data['title']} - full story on {niche['title']}, free on all podcast apps. #news #{niche_id.replace('-', '')}",
    }
    meta_path = f"logs/{niche_id}/{date}_short.json"
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"[done] {out_path} ({size_mb:.1f}MB, {meta['duration']}s) + {meta_path}")
    return True


def create_topic_short(topic_id: str, date: str) -> bool:
    """Event Short (e.g. World Cup): no episode behind it - stories come
    straight from Google News search, dedupe via the shared seen-registry."""
    topic = TOPICS[topic_id]
    if date >= topic["end_date"]:
        print(f"[skip] Topic '{topic_id}' ended on {topic['end_date']}")
        return True   # not an error - the slot just expires

    from fetch_news import _google_news_search, _load_seen, _mark_seen, _story_key

    # query may be a single string or a rotating list (evergreen lanes) — rotate
    # by day-of-year so each day pulls a different, always-on-topic search.
    query = topic["query"]
    if isinstance(query, list):
        doy = datetime.strptime(date, "%Y-%m-%d").timetuple().tm_yday
        query = query[doy % len(query)]
    print(f"[topic] {topic_id} query: {query!r}")
    items = _google_news_search(query, max_items=10)
    seen = _load_seen(f"topic-{topic_id}")
    fresh = [i for i in items if _story_key(i["title"]) not in seen]
    if not fresh:
        print(f"[skip] No fresh {topic_id} stories today")
        return True
    stories = [i["title"] for i in fresh[:5]]
    facts = "\n".join(f"- {i['title']}: {i['summary']}" for i in fresh[:5])

    pseudo_niche = {"id": topic_id, "title": topic["title"], "voice": topic["voice"]}
    data = _sanitize_packaging(write_short_script(pseudo_niche, stories, facts))

    os.makedirs("shorts", exist_ok=True)
    out_path = f"shorts/{topic_id}_{date}.mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        mp3 = os.path.join(tmpdir, "voice.mp3")
        words = synthesize(data["script"], topic["voice"], mp3)
        if not words:
            print("[error] TTS produced no word timings")
            return False
        duration = get_audio_duration(mp3)

        ass = os.path.join(tmpdir, "caps.ass")
        build_ass(words, duration, topic["cta_show"], ass, overlay=data.get("overlay", ""))

        img = os.path.join(tmpdir, "bg.jpg")
        if not fetch_vertical_image(topic_id, data.get("image_prompt", data["story"]), img):
            img = "assets/cover_trending.png"
            print(f"[short] Using cover fallback: {img}")

        if not render_short(img, mp3, ass, out_path):
            return False

    blurb = topic.get("blurb") or f"Daily {topic['title']} in under a minute."
    meta = {
        "niche":    topic_id,
        "date":     date,
        "story":    data["story"],
        "title":    data["title"],
        "overlay":  data.get("overlay", ""),
        "script":   data["script"],
        "duration": round(get_audio_duration(out_path), 1),
        "video":    out_path,
        # Topic Shorts carry their own upload metadata (no niche config)
        "category": topic["category"],
        "tags":     topic["tags"],
        "description": (
            f"{data['story']}\n\n"
            f"{blurb} "
            f"For everything the world is talking about today, listen to "
            f"{topic['cta_show']} - free on every podcast app.\n\n"
            f"All daily briefings: https://daily.mapt.cloud\n\n"
            f"{topic['hashtags']} #VeloxDaily\n"
        ),
        "tiktok_caption": f"{data['title']} - daily on Velox. {topic['hashtags']}",
    }
    meta_path = f"logs/{topic_id}/{date}_short.json"
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    _mark_seen(f"topic-{topic_id}", [{"title": data["story"]}])
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"[done] {out_path} ({size_mb:.1f}MB, {meta['duration']}s) + {meta_path}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", required=True)
    parser.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    if args.niche in TOPICS:
        sys.exit(0 if create_topic_short(args.niche, args.date) else 1)
    sys.exit(0 if create_short(args.niche, args.date) else 1)
