# -*- coding: utf-8 -*-
"""
Resolve ONE relevant image URL for an article. Openverse (CC0/PDM preferred,
then any commercially-usable), with a keyworded LoremFlickr fallback so we
always return something. Resolved once at article-build time and cached in the
article JSON (never called per page render).
"""
import json, os, re, urllib.request, urllib.parse

OV = "https://api.openverse.org/v1/images/"
UA = {"User-Agent": "MaptDaily/1.0 (+https://daily.mapt.cloud)"}
RASTER = (".jpg", ".jpeg", ".png", ".webp")


def _loremflickr(query, seed, w, h):
    tags = ",".join(re.findall(r"[a-z]{3,}", (query or "").lower())[:3]) or "news"
    return f"https://loremflickr.com/{w}/{h}/{urllib.parse.quote(tags)}?lock={seed % 9973}"


def _openverse(q, params):
    url = OV + "?" + urllib.parse.urlencode(dict(q=q, page_size=12, mature="false", **params))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r).get("results", [])


def fetch_image(query, seed=0, w=900, h=520):
    """Return a relevant image URL for `query`. Never raises."""
    q = (query or "").strip()
    if not q:
        return _loremflickr(q, seed, w, h)
    for params in ({"license": "cc0,pdm"}, {"license_type": "commercial"}):
        try:
            for res in _openverse(q, params):
                u = res.get("url", "")
                if u.lower().endswith(RASTER):
                    return u
        except Exception:
            pass
    return _loremflickr(q, seed, w, h)


def _cover_resize(data: bytes, w: int, h: int):
    """Cover-crop the raw image bytes to exactly w×h (uniform card size). Openverse
    returns full-res originals (some 6000px / 13 MB), which make cards render blank
    while they slowly download — so every cached image is normalised to ~900×520."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    sw, sh = im.size
    scale = max(w / sw, h / sh)
    nw, nh = max(w, int(sw * scale + 0.5)), max(h, int(sh * scale + 0.5))
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return im.crop((left, top, left + w, top + h))


def fetch_and_cache_image(query, subdir, name, seed=0, w=900, h=520):
    """Resolve an image via fetch_image() and download it to assets/<subdir>/<name>.jpg so the
    site serves it same-origin instead of hotlinking a third-party host at render time. The image
    is re-encoded to a web-sized w×h JPEG (never the multi-MB original). Returns the local web
    path, or the remote URL as a fallback if the download fails. Never raises. Skips if cached."""
    remote = fetch_image(query, seed, w, h)
    if not remote:
        return ""
    dest_dir = os.path.join("assets", *subdir.split("/"))
    dest_path = os.path.join(dest_dir, f"{name}.jpg")   # always re-encoded to jpg
    web_path = f"/assets/{subdir}/{name}.jpg"
    if os.path.exists(dest_path):
        return web_path
    try:
        req = urllib.request.Request(remote, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        os.makedirs(dest_dir, exist_ok=True)
        try:
            _cover_resize(data, w, h).save(dest_path, "JPEG", quality=82, optimize=True)
        except Exception as e:                          # PIL missing/decoding fail: save raw
            print(f"[fetch_image] resize failed ({e}); saving original bytes")
            with open(dest_path, "wb") as f:
                f.write(data)
        return web_path
    except Exception as e:
        print(f"[fetch_image] download failed, falling back to remote URL: {e}")
        return remote


if __name__ == "__main__":
    for t in ["bitcoin trading screen", "alzheimer brain research", "startup funding office"]:
        print(t, "->", fetch_image(t, 7))
