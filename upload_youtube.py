"""
Upload all podcast episodes to a single YouTube channel.
- One channel hosts all 7 niches, organised by playlists
- One refresh token (YT_REFRESH_TOKEN) in GitHub Secrets
- Playlist IDs auto-created on first run, stored in logs/yt_playlists.json
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


def build_title(niche: dict, episode_number: int, top_story: str = "") -> str:
    """SEO title: lead with the actual story, end with show name."""
    if top_story:
        # Clean up the story headline for a title
        story = top_story.encode("ascii", errors="ignore").decode("ascii").strip()
        story = story[:70].rsplit(" ", 1)[0] if len(story) > 70 else story
        return f"{story} | {niche['title']}"
    # Fallback if no story
    today = datetime.utcnow().strftime("%b %d, %Y")
    return f"{niche['title']} — Daily News Brief {today}"


def build_description(niche: dict, episode_number: int, script_excerpt: str = "",
                      stories: list = None) -> str:
    spotify_url = niche.get("spotify_url", "")
    today_long  = datetime.utcnow().strftime("%B %d, %Y")
    today_short = datetime.utcnow().strftime("%b %d")

    # Build timestamps block from stories (approx 60s each)
    timestamps = ""
    if stories:
        lines = ["00:00 Intro"]
        for i, s in enumerate(stories[:5]):
            mm = (i + 1) * 1
            lines.append(f"0{mm}:00 {s[:60].encode('ascii', errors='ignore').decode('ascii')}")
        timestamps = "\n".join(lines)

    # Hashtags from niche
    niche_tag = niche["title"].replace(" ", "")
    nid_tags  = {
        "ai-tech":    "#AI #ArtificialIntelligence #Tech #MachineLearning #OpenAI",
        "finance":    "#Finance #Investing #StockMarket #PersonalFinance #Economy",
        "health":     "#Health #Wellness #Longevity #Nutrition #MedicalNews",
        "startup":    "#Startup #VentureCapital #Founders #Business #Innovation",
        "crypto":     "#Crypto #Bitcoin #Ethereum #DeFi #Web3 #Blockchain",
        "world-news": "#WorldNews #Politics #International #BreakingNews #Global",
        "true-crime": "#TrueCrime #Crime #Investigation #Murder #TrueCrimePodcast",
    }.get(niche["id"], "#Podcast #News #Daily")

    script_block = ""
    if script_excerpt:
        clean = script_excerpt[:1000].encode("ascii", errors="ignore").decode("ascii")
        script_block = f"\n{clean}\n"

    return f"""Your daily {niche['title']} brief — {today_long}.

{niche['description']}
{script_block}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIMESTAMPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{timestamps if timestamps else "00:00 Full Episode"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LISTEN FREE ON ALL PLATFORMS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎧 Spotify  : {spotify_url}
🎙️  Search   : "{niche['title']}" on Apple Podcasts, Amazon Music, Pocket Casts

New episode every single day. Subscribe so you never miss one.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{nid_tags} #{niche_tag} #DailyPodcast #DailyNews #FreeP odcast
"""


def generate_thumbnail(niche_id: str, top_story: str, out_path: str) -> bool:
    """Generate a unique 1280x720 thumbnail from Pollinations for this episode."""
    import urllib.request, urllib.parse, time
    THUMB_STYLE = {
        "ai-tech":    "bold tech magazine cover style, glowing AI circuit brain, deep blue purple, dramatic lighting",
        "finance":    "bold financial magazine cover, stock chart arrows, gold coins, dark navy background",
        "health":     "clean health magazine cover, medical symbols, bright green white, modern minimal",
        "startup":    "startup pitch deck style, rocket launch, bold typography space, deep purple orange",
        "crypto":     "crypto news thumbnail, bitcoin logo glow, neon cyan black, cyberpunk dramatic",
        "world-news": "breaking news broadcast style, globe graphic, bold red white blue, urgent look",
        "true-crime": "true crime documentary thumbnail, dark shadowy, red spotlight, crime scene tape",
    }
    style = THUMB_STYLE.get(niche_id, "bold news thumbnail, dramatic lighting, vibrant colors")
    topic = top_story[:80].encode("ascii", errors="ignore").decode("ascii")
    prompt = f"{style}, topic: {topic}, no text, no words, cinematic composition, high contrast"
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


def upload_to_youtube(youtube, video_path: str, title: str, description: str, category_id: str = "25"):
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
        "world-news": "assets/cover_world.png",
        "true-crime": "assets/cover_truecrime.png",
    }
    cover_path = cover_map.get(args.niche, "assets/cover.png")

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "episode.mp4")
        print(f"[video] Building animated video for {args.niche}...")
        ep_title   = args.excerpt[:80] if args.excerpt else build_title(niche, args.number)
        story_list = [s.strip() for s in args.stories.split("||") if s.strip()] if args.stories else []
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
        title       = build_title(niche, args.number, top_story)
        desc        = build_description(niche, args.number, args.excerpt, story_list)
        category_id = CATEGORY_IDS.get(args.niche, "25")
        video_id    = upload_to_youtube(youtube, video_path, title, desc, category_id)

        # Upload unique thumbnail
        thumb_path = os.path.join(tmpdir, "thumbnail.jpg")
        if generate_thumbnail(args.niche, top_story, thumb_path):
            try:
                upload_thumbnail(youtube, video_id, thumb_path)
            except Exception as e:
                print(f"[thumbnail] Upload failed (non-fatal): {e}")

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
