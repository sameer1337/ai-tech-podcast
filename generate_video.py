"""
Generate an animated YouTube video for a podcast episode.

Pipeline:
  1. Fetch one cartoon image per story headline from Pollinations.ai (free, no key)
  2. Calculate per-segment duration from actual audio length
  3. Build xfade transition chain (different transition per cut) via FFmpeg
  4. Overlay animated tri-colour waveform throughout
  5. Output final MP4

Usage:
  python generate_video.py --niche ai-tech --audio ep.mp3 --title "Title"
         --stories "Story 1||Story 2||Story 3" --out out.mp4
"""

import os
import sys
import json
import re
import subprocess
import tempfile
import argparse
import urllib.request
import urllib.parse
import time
import random


# ── FFmpeg path ────────────────────────────────────────────────────────────────

def get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


# ── Per-niche style prefix for all image prompts ───────────────────────────────

NICHE_STYLE = {
    "ai-tech":    "futuristic cartoon illustration style, vibrant blues and purples, glowing tech aesthetic",
    "finance":    "bold cartoon illustration, gold and green tones, financial district skyline style",
    "health":     "bright cheerful cartoon illustration, clean medical aesthetic, colourful health icons",
    "startup":    "energetic cartoon illustration, modern startup office, warm vibrant colours",
    "crypto":     "neon cyberpunk cartoon illustration, cyan and orange glow, digital blockchain aesthetic",
    "world-news": "bold viral-story cartoon illustration, fiery red orange gradient, dramatic energetic",
    "true-crime": "noir cartoon illustration, moody blue-purple shadows, detective mystery aesthetic",
}

FALLBACK_COVERS = {
    "ai-tech":    "assets/cover.png",
    "finance":    "assets/cover_finance.png",
    "health":     "assets/cover_health.png",
    "startup":    "assets/cover_startup.png",
    "crypto":     "assets/cover_crypto.png",
    "world-news": "assets/cover_trending.png",
    "true-crime": "assets/cover_truecrime.png",
}

# FFmpeg xfade transitions — variety per cut
TRANSITIONS = [
    "fade", "slideleft", "slideright", "wipeleft", "wiperight",
    "dissolve", "circleopen", "radial", "smoothleft", "smoothright",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_audio_duration(audio_path: str) -> float:
    """Return audio duration in seconds via ffprobe."""
    ffmpeg = get_ffmpeg()
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    if not os.path.exists(ffprobe):
        # imageio_ffmpeg doesn't ship ffprobe — use ffmpeg itself to read duration
        cmd = [ffmpeg, "-i", audio_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        for line in result.stderr.splitlines():
            if "Duration" in line:
                parts = line.strip().split("Duration:")[1].split(",")[0].strip()
                h, m, s = parts.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
        return 300.0  # fallback 5 min
    cmd = [
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "json", audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 300.0


def fetch_story_image(niche_id: str, story: str, out_path: str, seed: int) -> bool:
    """Fetch a cartoon image for a single story headline."""
    style = NICHE_STYLE.get(niche_id, "colourful cartoon illustration, vibrant, no text")
    topic = story[:80].replace("|", "").strip()
    # Strip non-ASCII characters (arrows, smart quotes, etc.) to avoid charmap errors
    topic = topic.encode("ascii", errors="ignore").decode("ascii")
    prompt = f"{style}, scene: {topic}, no text, no words, no captions"
    encoded = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1920&height=1080&nologo=true&model=flux&seed={seed % 99999}"
    )
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "podcast-bot/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 5000:
                raise ValueError(f"Response too small ({len(data)} bytes)")
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"  [img {seed}] {story[:50]} -> {len(data)//1024}KB")
            return True
        except Exception as e:
            print(f"  [img {seed}] attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(8)
    return False


def fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(script: str, duration: float, srt_path: str):
    """Split script into subtitle lines timed proportionally by character count."""
    # Split into sentences, then wrap long ones at ~60 chars
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    lines = []
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        while len(sent) > 60:
            cut = sent[:60].rfind(' ')
            cut = cut if cut > 15 else 60
            lines.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if sent:
            lines.append(sent)

    if not lines:
        return

    total_chars = sum(len(l) for l in lines) or 1
    with open(srt_path, "w", encoding="utf-8") as f:
        t = 0.0
        for i, line in enumerate(lines):
            seg = max(1.0, (len(line) / total_chars) * duration)
            end = min(t + seg, duration)
            f.write(f"{i + 1}\n{fmt_srt_time(t)} --> {fmt_srt_time(end)}\n{line}\n\n")
            t = end
            if t >= duration:
                break


def scale_filter(label_in: str, label_out: str) -> str:
    return (
        f"[{label_in}]scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[{label_out}]"
    )


def build_xfade_video(image_paths: list, audio_path: str, out_path: str,
                      srt_path: str = None) -> bool:
    """
    Build final video:
      - N images, each shown for audio_duration/N seconds
      - xfade transitions (1.5s each) between segments
      - tri-colour animated waveform overlay at bottom
    """
    n = len(image_paths)
    duration = get_audio_duration(audio_path)
    seg = duration / n          # seconds per image
    trans_dur = min(1.5, seg * 0.15)  # transition = 15% of segment, max 1.5s

    ffmpeg = get_ffmpeg()
    inputs = []
    for p in image_paths:
        inputs += ["-loop", "1", "-t", f"{seg + trans_dur:.2f}", "-i", p]
    inputs += ["-i", audio_path]
    audio_idx = n  # audio is the last input

    # Build filter_complex
    fc = []

    # Scale each image
    for i in range(n):
        fc.append(scale_filter(f"{i}:v", f"s{i}"))

    # Chain xfade transitions
    trans_list = random.sample(TRANSITIONS * 3, n - 1)  # random, no repeats
    prev = "s0"
    for i in range(1, n):
        offset = i * seg - trans_dur / 2
        t = trans_list[i - 1]
        out_label = f"x{i}" if i < n - 1 else "xout"
        fc.append(
            f"[{prev}][s{i}]xfade=transition={t}:duration={trans_dur:.2f}"
            f":offset={offset:.2f}[{out_label}]"
        )
        prev = out_label

    final_v = "xout" if n > 1 else "s0"

    # Waveform + dark strip overlay
    fc += [
        f"[{audio_idx}:a]showwaves=s=1920x180:mode=cline"
        ":colors=0x00e5ff@0.9|0xff6b35@0.9|0x7fff00@0.9:scale=sqrt[waves]",
        "[waves]format=rgba[wavesrgba]",
        "color=c=0x000000@0.65:s=1920x200[bgstrip]",
        f"[{final_v}][bgstrip]overlay=0:880[base]",
        "[base][wavesrgba]overlay=0:890[vwave]",
    ]

    # Burn subtitles if SRT provided
    if srt_path and os.path.exists(srt_path):
        # Use forward slashes and escape colons for FFmpeg on Windows
        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
        fc.append(
            f"[vwave]subtitles='{srt_escaped}'"
            ":force_style='FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BackColour=&H80000000,Outline=2,Shadow=1,"
            "Bold=1,Alignment=2,MarginV=110'[v]"
        )
        final_label = "v"
    else:
        # Rename last label to v for map consistency
        fc[-1] = fc[-1].replace("[vwave]", "[vwave]").rstrip("]") + "]"
        fc.append(f"[vwave]copy[v]")
        final_label = "v"

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", ";".join(fc),
        "-map", "[v]",
        "-map", f"{audio_idx}:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        out_path,
    ]

    print(f"  [ffmpeg] Rendering {n}-scene video ({duration:.0f}s audio, {seg:.0f}s/scene)...")
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print("[ffmpeg error]", result.stderr.decode()[-1000:])
        return False
    return True


# ── Main entry point ───────────────────────────────────────────────────────────

def create_animated_video(
    niche_id: str,
    audio_path: str,
    episode_title: str,
    out_path: str,
    stories: list = None,
    script: str = "",
) -> bool:
    """
    Full pipeline:
      - stories: list of story headline strings (3-5 recommended)
      - Falls back to single niche-themed image if no stories provided
    """
    # Build image prompt list from stories + episode title as opener
    if not stories:
        stories = [episode_title]

    # Cap at 5 scenes — more than that makes each scene too short
    scenes = ([episode_title] + stories)[:5]
    # Deduplicate while preserving order
    seen = set()
    scenes = [s for s in scenes if not (s in seen or seen.add(s))]

    with tempfile.TemporaryDirectory() as tmpdir:
        image_paths = []
        fallback = FALLBACK_COVERS.get(niche_id, "assets/cover.png")

        for i, scene in enumerate(scenes):
            img_path = os.path.join(tmpdir, f"scene_{i:02d}.jpg")
            seed = abs(hash(scene + niche_id + str(i)))
            ok = fetch_story_image(niche_id, scene, img_path, seed)
            if ok:
                image_paths.append(img_path)
            elif os.path.exists(fallback):
                print(f"  [fallback] Using cover for scene {i}")
                image_paths.append(fallback)
            else:
                print(f"  [skip] No image for scene {i}")

        if not image_paths:
            print("[error] No images available — aborting")
            return False

        # Generate SRT subtitles from script
        srt_path = None
        if script and script.strip():
            srt_path = os.path.join(tmpdir, "subtitles.srt")
            duration = get_audio_duration(audio_path)
            generate_srt(script, duration, srt_path)
            print(f"  [srt] Subtitles generated")

        print(f"  [video] Building {len(image_paths)}-scene video...")
        if not build_xfade_video(image_paths, audio_path, out_path, srt_path=srt_path):
            return False

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"  [done] {out_path} ({size_mb:.1f}MB, {len(image_paths)} scenes)")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche",       required=True)
    parser.add_argument("--audio",       required=True)
    parser.add_argument("--title",       default="Podcast Episode")
    parser.add_argument("--stories",     default="", help="Story headlines separated by ||")
    parser.add_argument("--script-file", default="", help="Path to script .txt for subtitles")
    parser.add_argument("--out",         required=True)
    args = parser.parse_args()

    story_list = [s.strip() for s in args.stories.split("||") if s.strip()] if args.stories else []
    script_text = ""
    if args.script_file and os.path.exists(args.script_file):
        with open(args.script_file, encoding="utf-8") as f:
            script_text = f.read()
    ok = create_animated_video(args.niche, args.audio, args.title, args.out,
                               stories=story_list, script=script_text)
    sys.exit(0 if ok else 1)
