"""
Generate podcast cover art as PNG files using Pillow (free, no API needed).
Creates professional-looking covers with gradient backgrounds + text.
"""

import os
import math

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import subprocess
    subprocess.run(["pip", "install", "pillow", "-q"], check=True)
    from PIL import Image, ImageDraw, ImageFont

SIZE = 3000

COVERS = [
    {
        "id":       "finance",
        "filename": "assets/cover_finance.png",
        "title":    "MONEY\nMINUTE\nDAILY",
        "tagline":  "Daily Finance & Markets",
        "bg1":      (10, 20, 50),
        "bg2":      (0, 80, 40),
        "accent":   (255, 200, 0),
        "emoji":    "$",
    },
    {
        "id":       "health",
        "filename": "assets/cover_health.png",
        "title":    "HEALTH\nEDGE\nDAILY",
        "tagline":  "Daily Health & Longevity",
        "bg1":      (5, 30, 40),
        "bg2":      (0, 80, 70),
        "accent":   (0, 220, 180),
        "emoji":    "+",
    },
    {
        "id":       "startup",
        "filename": "assets/cover_startup.png",
        "title":    "STARTUP\nWIRE\nDAILY",
        "tagline":  "Venture Capital & Startups",
        "bg1":      (20, 5, 50),
        "bg2":      (80, 0, 100),
        "accent":   (180, 100, 255),
        "emoji":    ">>",
    },
    {
        "id":       "crypto",
        "filename": "assets/cover_crypto.png",
        "title":    "CRYPTO\nDAILY\nBRIEF",
        "tagline":  "Bitcoin & Web3 News",
        "bg1":      (10, 15, 40),
        "bg2":      (80, 40, 0),
        "accent":   (255, 165, 0),
        "emoji":    "B",
    },
    {
        # Rebrand of World In 5 (same feed/id world-news) - trends show
        "id":       "trending",
        "filename": "assets/cover_trending.png",
        "title":    "TRENDING\nNOW\nDAILY",
        "tagline":  "What The World Is Searching",
        "bg1":      (30, 0, 10),
        "bg2":      (120, 20, 0),
        "accent":   (255, 80, 40),
        "emoji":    "#",
    },
    {
        "id":       "truecrime",
        "filename": "assets/cover_truecrime.png",
        "title":    "TRUE\nCRIME\nDIGEST",
        "tagline":  "Daily True Crime Stories",
        "bg1":      (10, 0, 0),
        "bg2":      (50, 0, 20),
        "accent":   (220, 50, 50),
        "emoji":    "!",
    },
]


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def make_gradient(size, color1, color2):
    img = Image.new("RGB", (size, size))
    pixels = img.load()
    for y in range(size):
        t = y / size
        # diagonal gradient
        color = lerp_color(color1, color2, t)
        for x in range(size):
            tx = x / size
            blended = lerp_color(color, lerp_color(color1, color2, tx), 0.3)
            pixels[x, y] = blended
    return img


def draw_circles(draw, size, accent):
    # Decorative circles in background
    r, g, b = accent
    for i, (cx, cy, radius, alpha) in enumerate([
        (size * 0.8, size * 0.2, size * 0.35, 25),
        (size * 0.1, size * 0.75, size * 0.25, 20),
        (size * 0.5, size * 0.5, size * 0.45, 10),
    ]):
        overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
        d.ellipse(bbox, outline=(r, g, b, alpha), width=max(3, size // 200))
        base = draw._image.convert("RGBA")
        base.alpha_composite(overlay)
        draw._image.paste(base.convert("RGB"))


def make_cover(cfg):
    size = SIZE
    img = make_gradient(size, cfg["bg1"], cfg["bg2"])
    draw = ImageDraw.Draw(img)

    # Decorative circles
    accent = cfg["accent"]
    for cx, cy, radius, alpha_val in [
        (size * 0.82, size * 0.18, size * 0.32, 30),
        (size * 0.12, size * 0.78, size * 0.22, 22),
        (size * 0.5,  size * 0.5,  size * 0.48, 12),
    ]:
        # draw ring
        for thickness in range(max(2, size // 300)):
            r = radius - thickness
            draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                outline=(*accent, ),
                width=1,
            )

    # Accent bar on left
    bar_w = size // 30
    draw.rectangle([size // 15, size // 6, size // 15 + bar_w, size * 5 // 6],
                   fill=accent)

    # Try to load a font, fall back to default
    font_size_title  = size // 7
    font_size_tag    = size // 22
    font_size_emoji  = size // 5
    try:
        font_title  = ImageFont.truetype("arialbd.ttf",  font_size_title)
        font_tag    = ImageFont.truetype("arial.ttf",    font_size_tag)
        font_emoji  = ImageFont.truetype("arialbd.ttf",  font_size_emoji)
    except Exception:
        font_title  = ImageFont.load_default(size=font_size_title)
        font_tag    = ImageFont.load_default(size=font_size_tag)
        font_emoji  = ImageFont.load_default(size=font_size_emoji)

    # Large emoji/symbol bottom-right
    draw.text((size * 0.6, size * 0.45), cfg["emoji"],
              font=font_emoji, fill=(*accent, ), anchor="mm" if hasattr(font_emoji, 'getbbox') else None)

    # Title text
    margin_left = size // 7
    y = size // 5
    for line in cfg["title"].split("\n"):
        draw.text((margin_left, y), line, font=font_title, fill=(255, 255, 255))
        y += font_size_title + size // 40

    # Tagline
    draw.text((margin_left, size * 0.82), cfg["tagline"],
              font=font_tag, fill=(*accent,))

    # Bottom accent line
    draw.rectangle([0, size - size // 40, size, size], fill=accent)

    os.makedirs("assets", exist_ok=True)
    img.save(cfg["filename"], "PNG", quality=95)
    print(f"[cover] Saved {cfg['filename']}")


if __name__ == "__main__":
    print("Generating cover art for all 6 podcasts...")
    for cfg in COVERS:
        try:
            make_cover(cfg)
        except Exception as e:
            print(f"[cover] ERROR for {cfg['id']}: {e}")
    print("Done!")
