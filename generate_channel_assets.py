"""
Generate YouTube channel logos + banners for all 6 remaining niches.
Downloads to assets/channels/{niche}/logo.png and banner.png

Run once:
  python generate_channel_assets.py
"""

import os
import time
import urllib.request
import urllib.parse

CHANNELS = {
    "finance": {
        "name": "Money Minute Daily",
        "color": "0A2540",
        "accent": "F0C040",
        "logo_prompt": "minimal flat logo, large gold coin with upward bar chart arrow, dark navy background #0A2540, gold #F0C040 icon centered, no text, clean vector style, podcast logo",
        "banner_prompt": "youtube channel banner, dark navy #0A2540 background, bold gold text MONEY MINUTE DAILY, gold coin and stock chart icons, clean professional finance design, 2560x1440 wide format, no clutter",
    },
    "health": {
        "name": "Health Edge Daily",
        "color": "0D3B2E",
        "accent": "5EE8A0",
        "logo_prompt": "minimal flat logo, mint green leaf with heartbeat pulse line through it, deep green background #0D3B2E, mint #5EE8A0 icon centered, no text, clean vector style, podcast logo",
        "banner_prompt": "youtube channel banner, deep green #0D3B2E background, bold mint green text HEALTH EDGE DAILY, leaf and heartbeat pulse icons, clean modern health wellness design, 2560x1440 wide format, no clutter",
    },
    "startup": {
        "name": "Startup Wire Daily",
        "color": "1A0A3C",
        "accent": "FF6B6B",
        "logo_prompt": "minimal flat logo, red rocket launching upward with speed lines, deep purple background #1A0A3C, red #FF6B6B rocket icon centered, no text, clean vector style, podcast logo",
        "banner_prompt": "youtube channel banner, deep purple #1A0A3C background, bold red text STARTUP WIRE DAILY, rocket and lightning bolt icons, energetic startup tech design, 2560x1440 wide format, no clutter",
    },
    "crypto": {
        "name": "Crypto Daily Brief",
        "color": "0A0A1A",
        "accent": "00E5FF",
        "logo_prompt": "minimal flat logo, bitcoin B symbol inside hexagon, near black background #0A0A1A, electric cyan #00E5FF icon centered, neon glow effect, no text, clean vector style, podcast logo",
        "banner_prompt": "youtube channel banner, near black #0A0A1A background, bold electric cyan text CRYPTO DAILY BRIEF, bitcoin hexagon and blockchain nodes icons, cyberpunk crypto design, 2560x1440 wide format, no clutter",
    },
    "world-news": {
        "name": "World In 5",
        "color": "1C1C2E",
        "accent": "E8E8F0",
        "logo_prompt": "minimal flat logo, simple globe with latitude longitude lines, midnight dark background #1C1C2E, off-white #E8E8F0 globe icon centered, no text, clean vector style, podcast logo",
        "banner_prompt": "youtube channel banner, midnight dark #1C1C2E background, bold off-white text WORLD IN 5, globe and newspaper icons, clean serious news design, 2560x1440 wide format, no clutter",
    },
    "true-crime": {
        "name": "True Crime Digest",
        "color": "1A0A0A",
        "accent": "FF4444",
        "logo_prompt": "minimal flat logo, magnifying glass overlapping fingerprint, dark crimson background #1A0A0A, blood red #FF4444 icon centered, no text, clean vector style, podcast logo",
        "banner_prompt": "youtube channel banner, dark crimson #1A0A0A background, bold red text TRUE CRIME DIGEST, magnifying glass and fingerprint icons, noir detective crime design, 2560x1440 wide format, no clutter",
    },
}

LOGO_SIZE   = "800x800"
BANNER_SIZE = "2560x1440"


def fetch_image(prompt: str, size: str, out_path: str, seed: int) -> bool:
    w, h = size.split("x")
    encoded = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={w}&height={h}&nologo=true&model=flux&seed={seed}"
    )
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "channel-asset-bot/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 8000:
                raise ValueError(f"Too small ({len(data)} bytes)")
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"  saved {os.path.basename(out_path)} ({len(data)//1024}KB)")
            return True
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}")
            if attempt < 3:
                time.sleep(12)
    return False


def main():
    base = os.path.join("assets", "channels")
    os.makedirs(base, exist_ok=True)

    for niche_id, cfg in CHANNELS.items():
        print(f"\n=== {cfg['name']} ===")
        out_dir = os.path.join(base, niche_id)
        os.makedirs(out_dir, exist_ok=True)

        seed_logo   = abs(hash(niche_id + "logo"))   % 99999
        seed_banner = abs(hash(niche_id + "banner")) % 99999

        logo_path   = os.path.join(out_dir, "logo.png")
        banner_path = os.path.join(out_dir, "banner.png")

        print(f"  Generating logo ({LOGO_SIZE})...")
        ok = fetch_image(cfg["logo_prompt"], LOGO_SIZE, logo_path, seed_logo)
        if not ok:
            print(f"  [WARN] Logo failed for {niche_id}")

        # Small pause between requests to avoid 429
        time.sleep(5)

        print(f"  Generating banner ({BANNER_SIZE})...")
        ok = fetch_image(cfg["banner_prompt"], BANNER_SIZE, banner_path, seed_banner)
        if not ok:
            print(f"  [WARN] Banner failed for {niche_id}")

        time.sleep(5)

    print("\n\nDone! Files saved to:")
    for niche_id in CHANNELS:
        d = os.path.join(base, niche_id)
        for f in ["logo.png", "banner.png"]:
            p = os.path.join(d, f)
            if os.path.exists(p):
                size_kb = os.path.getsize(p) // 1024
                print(f"  {p} ({size_kb}KB)")
            else:
                print(f"  {p} -- MISSING")

    print("\nUpload each logo as channel profile picture (800x800)")
    print("Upload each banner as channel art (YouTube uses center 1546x423 safe zone)")


if __name__ == "__main__":
    main()
