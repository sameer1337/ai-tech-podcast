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

# Per-niche vertical background style (distinct from the 16:9 episode style)
SHORT_STYLE = {
    "ai-tech":    "dramatic vertical poster, glowing AI circuitry, deep blue purple neon, cinematic",
    "finance":    "dramatic vertical poster, stock chart skyline, gold on dark navy, cinematic",
    "health":     "dramatic vertical poster, human silhouette with glowing anatomy, teal on dark, cinematic",
    "startup":    "dramatic vertical poster, rocket launch over city, warm orange purple, cinematic",
    "crypto":     "dramatic vertical poster, bitcoin neon glow, cyan black cyberpunk, cinematic",
    "world-news": "dramatic vertical poster, world map with red highlights, breaking news mood, cinematic",
    "true-crime": "dramatic vertical poster, noir crime scene, red spotlight in darkness, moody fog, cinematic",
}


# -- 1. Script ----------------------------------------------------------------

def write_short_script(niche: dict, stories: list, episode_script: str) -> dict:
    """Ask Groq for a hook-first Shorts script. Falls back to trimming the episode."""
    try:
        from groq import Groq
        from config import GROQ_API_KEY
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
- "image_prompt": 10-15 words describing one dramatic scene for this story"""
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
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
                model="llama-3.3-70b-versatile",
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

    # Fallback: first sentences of the episode script, capped ~85 words
    sents = re.split(r"(?<=[.!?])\s+", episode_script.strip())
    script, words = [], 0
    for s in sents:
        if words + len(s.split()) > 100:
            break
        script.append(s)
        words += len(s.split())
    top = stories[0] if stories else niche["title"]
    return {
        "story":        top,
        "overlay":      " ".join(top.split()[:6]),
        "script":       " ".join(script),
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


def build_ass(words: list, duration: float, show_title: str, ass_path: str):
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

    data = write_short_script(niche, stories, episode_script)

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
        build_ass(words, duration, niche["title"], ass)

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", required=True)
    parser.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    sys.exit(0 if create_short(args.niche, args.date) else 1)
