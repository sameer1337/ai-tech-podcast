"""
Generate an animated YouTube video for a podcast episode.

Pipeline:
  1. Fetch a cartoon/illustrated AI image from Pollinations.ai (free, no key needed)
     — topic prompt is built from episode title + niche
  2. Apply Ken Burns slow-zoom animation (30s loop) via FFmpeg zoompan
  3. Overlay animated audio waveform at the bottom
  4. Combine looped animation + audio → final MP4

Usage:
  python generate_video.py --niche ai-tech --audio ep.mp3 --title "Title" --out out.mp4
"""

import os
import sys
import subprocess
import tempfile
import argparse
import urllib.request
import urllib.parse
import time


def get_ffmpeg() -> str:
    """Return path to ffmpeg — prefers imageio_ffmpeg bundle (always present), falls back to system."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

# Per-niche cartoon image prompts for Pollinations.ai
NICHE_VISUAL_PROMPTS = {
    "ai-tech":    "futuristic robot reading holographic news feed, glowing circuits, cartoon illustration, vibrant blues and purples, tech aesthetic, no text",
    "finance":    "cartoon character in sharp suit watching stock market charts on multiple screens, financial district skyline, gold and green tones, illustrated style, no text",
    "health":     "cheerful cartoon doctor with stethoscope in bright modern clinic, colorful health icons floating around, clean illustration style, no text",
    "startup":    "energetic cartoon entrepreneur at whiteboard with rocket and lightbulb icons, modern startup office, warm vibrant colors, no text",
    "crypto":     "cartoon character surfing a wave of bitcoin coins and blockchain cubes, neon cyan and orange, digital cyberpunk illustration style, no text",
    "world-news": "cartoon globe with newspaper pages swirling around it, diverse world landmarks in background, bold colorful illustration, no text",
    "true-crime": "cartoon detective with magnifying glass and clues pinned to a board, moody blue-purple lighting, noir illustration style, shadows and mystery, no text",
}

FALLBACK_COVERS = {
    "ai-tech":    "assets/cover.png",
    "finance":    "assets/cover_finance.png",
    "health":     "assets/cover_health.png",
    "startup":    "assets/cover_startup.png",
    "crypto":     "assets/cover_crypto.png",
    "world-news": "assets/cover_world.png",
    "true-crime": "assets/cover_truecrime.png",
}


def fetch_cartoon_image(niche_id: str, episode_title: str, out_path: str) -> bool:
    """Download a cartoon-style image from Pollinations.ai. Returns True on success."""
    base_prompt = NICHE_VISUAL_PROMPTS.get(niche_id, "colorful cartoon podcast studio, microphone, vibrant illustration, no text")
    # Enrich with episode topic keywords (first 60 chars of title)
    topic = episode_title[:60].replace("|", "").strip()
    full_prompt = f"{base_prompt}, theme: {topic}"
    encoded = urllib.parse.quote(full_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&nologo=true&model=flux&seed={abs(hash(episode_title)) % 99999}"

    print(f"  [pollinations] Fetching image for: {niche_id}")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "podcast-bot/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if len(data) < 5000:
                raise ValueError(f"Response too small ({len(data)} bytes), likely an error")
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"  [pollinations] Image saved ({len(data)//1024}KB)")
            return True
        except Exception as e:
            print(f"  [pollinations] Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(10)

    print("  [pollinations] All attempts failed — will use fallback cover")
    return False


def create_video_with_waveform(image_path: str, audio_path: str, out_path: str) -> bool:
    """Single-pass FFmpeg: cartoon image + animated waveform overlay + audio → MP4."""
    cmd = [
        get_ffmpeg(), "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-filter_complex",
        # Resize image to exactly 1920x1080 (letterbox if needed)
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[img];"
        # Colourful waveform bars — splits into 3 colour bands for visual pop
        "[1:a]showwaves=s=1920x180:mode=cline:colors=0x00e5ff@0.9|0xff6b35@0.9|0x7fff00@0.9:scale=sqrt[waves];"
        "[waves]format=rgba[wavesrgba];"
        # Semi-transparent dark strip behind waveform for readability
        "color=c=0x000000@0.6:s=1920x200[bgstrip];"
        "[img][bgstrip]overlay=0:880[base];"
        "[base][wavesrgba]overlay=0:890[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print("[ffmpeg error]", result.stderr.decode()[-800:])
        return False
    return True


def create_animated_video(niche_id: str, audio_path: str, episode_title: str, out_path: str) -> bool:
    """Full pipeline: fetch cartoon image → overlay animated waveform → MP4."""
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "cartoon.jpg")

        # Step 1: get cartoon image (fallback to static cover on failure)
        success = fetch_cartoon_image(niche_id, episode_title, img_path)
        if not success:
            fallback = FALLBACK_COVERS.get(niche_id, "assets/cover.png")
            if os.path.exists(fallback):
                img_path = fallback
                print(f"  [fallback] Using static cover: {fallback}")
            else:
                print(f"  [error] No fallback cover found at {fallback}")
                return False

        # Step 2: image + waveform + audio → final MP4 (single pass)
        print("  [ffmpeg] Rendering video with animated waveform...")
        if not create_video_with_waveform(img_path, audio_path, out_path):
            return False

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"  [done] Video ready: {out_path} ({size_mb:.1f}MB)")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche",   required=True)
    parser.add_argument("--audio",   required=True)
    parser.add_argument("--title",   default="Podcast Episode")
    parser.add_argument("--out",     required=True)
    args = parser.parse_args()

    ok = create_animated_video(args.niche, args.audio, args.title, args.out)
    sys.exit(0 if ok else 1)
