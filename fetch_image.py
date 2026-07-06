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


def fetch_and_cache_image(query, subdir, name, seed=0, w=900, h=520):
    """Resolve an image via fetch_image() and download it to assets/<subdir>/<name>.ext so the
    site serves it same-origin instead of hotlinking a third-party host at render time. Returns
    the local web path (e.g. "/assets/blog/ai-tech/123.jpg"), or the remote URL as a fallback if
    the download fails. Never raises. Skips re-downloading if already cached on disk."""
    remote = fetch_image(query, seed, w, h)
    if not remote:
        return ""
    m = re.search(r"\.(jpe?g|png|webp)(?:$|\?)", remote, re.IGNORECASE)
    ext = f".{m.group(1).lower()}" if m else ".jpg"
    dest_dir = os.path.join("assets", *subdir.split("/"))
    dest_path = os.path.join(dest_dir, f"{name}{ext}")
    web_path = f"/assets/{subdir}/{name}{ext}"
    if os.path.exists(dest_path):
        return web_path
    try:
        req = urllib.request.Request(remote, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        os.makedirs(dest_dir, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        return web_path
    except Exception as e:
        print(f"[fetch_image] download failed, falling back to remote URL: {e}")
        return remote


if __name__ == "__main__":
    for t in ["bitcoin trading screen", "alzheimer brain research", "startup funding office"]:
        print(t, "->", fetch_image(t, 7))
