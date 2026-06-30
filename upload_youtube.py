"""
Upload a podcast episode to YouTube.
- Creates a video: cover image (static) + MP3 audio via FFmpeg
- Uploads to YouTube via Data API v3 using a stored refresh token
Usage: python upload_youtube.py --niche ai-tech --episode episodes/ep0001_2026-06-29.mp3
"""

import os
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

# ── Per-channel YouTube config ─────────────────────────────────────────────
# Add channel ID and refresh token secret name for each niche
YOUTUBE_CONFIG = {
    "ai-tech": {
        "channel_id":    "UCtyXT1jjL0Un-w3Bqo5l68g",
        "refresh_token": os.environ.get("YT_REFRESH_TOKEN_AI_TECH", ""),
    },
    "finance": {
        "channel_id":    "",
        "refresh_token": os.environ.get("YT_REFRESH_TOKEN_FINANCE", ""),
    },
    "health": {
        "channel_id":    "",
        "refresh_token": os.environ.get("YT_REFRESH_TOKEN_HEALTH", ""),
    },
    "startup": {
        "channel_id":    "",
        "refresh_token": os.environ.get("YT_REFRESH_TOKEN_STARTUP", ""),
    },
    "crypto": {
        "channel_id":    "",
        "refresh_token": os.environ.get("YT_REFRESH_TOKEN_CRYPTO", ""),
    },
    "world-news": {
        "channel_id":    "",
        "refresh_token": os.environ.get("YT_REFRESH_TOKEN_WORLD", ""),
    },
    "true-crime": {
        "channel_id":    "",
        "refresh_token": os.environ.get("YT_REFRESH_TOKEN_TRUECRIME", ""),
    },
}

GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_youtube_client(refresh_token: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def create_video(audio_path: str, cover_path: str, out_path: str) -> bool:
    """Use FFmpeg to combine static cover image + audio into MP4."""
    cmd = [
        "ffmpeg", "-y",
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


def build_title(niche: dict, episode_number: int) -> str:
    today = datetime.utcnow().strftime("%b %d")
    return f"{niche['title']} | {today} — Episode {episode_number}"


def build_description(niche: dict, episode_number: int, script_excerpt: str = "") -> str:
    return f"""{niche['description']}

{'—' * 40}
Episode {episode_number} | {datetime.utcnow().strftime('%B %d, %Y')}

{script_excerpt[:800] if script_excerpt else ''}

{'—' * 40}
🎙️ Listen on all podcast platforms — search "{niche['title']}"
📡 RSS Feed: https://sameer1337.github.io/ai-tech-podcast/{niche['rss_file']}
🌐 Website: https://sameer1337.github.io/ai-tech-podcast/podcasts/{niche['id']}/

#Podcast #Daily #Free #{niche['title'].replace(' ', '')}
"""


def upload_to_youtube(youtube, video_path: str, title: str, description: str, category_id: str = "22"):
    print(f"[youtube] Uploading: {title}")
    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "categoryId":  category_id,
            "tags":        ["podcast", "daily", "free", "audio"],
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024*5)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"[youtube] Upload {pct}%", end="\r")

    print(f"\n[youtube] Done → https://youtu.be/{response['id']}")
    return response["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche",   required=True, help="Niche ID e.g. ai-tech")
    parser.add_argument("--episode", required=True, help="Path to MP3 file")
    parser.add_argument("--number",  type=int, default=1, help="Episode number")
    parser.add_argument("--excerpt", default="", help="Script excerpt for description")
    args = parser.parse_args()

    niche = PODCAST_MAP.get(args.niche)
    if not niche:
        print(f"[error] Unknown niche: {args.niche}")
        sys.exit(1)

    yt_cfg = YOUTUBE_CONFIG.get(args.niche, {})
    refresh_token = yt_cfg.get("refresh_token", "")
    if not refresh_token:
        print(f"[skip] No refresh token for {args.niche} — skipping YouTube upload")
        sys.exit(0)

    # Cover image path
    cover_map = {
        "ai-tech":    "assets/cover.png",
        "finance":    "assets/cover_finance.png",
        "health":     "assets/cover_health.png",
        "startup":    "assets/cover_startup.png",
        "crypto":     "assets/cover_crypto.png",
        "world-news": "assets/cover_world.png",
        "true-crime": "assets/cover_truecrime.png",
    }
    cover_path = cover_map.get(args.niche, "assets/cover.png")

    # Create video in temp dir
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "episode.mp4")
        print(f"[ffmpeg] Creating video from {args.episode} + {cover_path}")
        if not create_video(args.episode, cover_path, video_path):
            print("[error] FFmpeg failed")
            sys.exit(1)

        youtube   = get_youtube_client(refresh_token)
        title     = build_title(niche, args.number)
        desc      = build_description(niche, args.number, args.excerpt)
        video_id  = upload_to_youtube(youtube, video_path, title, desc)

    print(f"[done] https://youtu.be/{video_id}")


if __name__ == "__main__":
    main()
