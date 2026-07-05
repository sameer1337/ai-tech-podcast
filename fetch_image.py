# -*- coding: utf-8 -*-
"""
Resolve ONE relevant image URL for an article. Openverse (CC0/PDM preferred,
then any commercially-usable), with a keyworded LoremFlickr fallback so we
always return something. Resolved once at article-build time and cached in the
article JSON (never called per page render).
"""
import json, re, urllib.request, urllib.parse

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


if __name__ == "__main__":
    for t in ["bitcoin trading screen", "alzheimer brain research", "startup funding office"]:
        print(t, "->", fetch_image(t, 7))
