# -*- coding: utf-8 -*-
"""
submit_indexnow.py — ping IndexNow (Bing, Yandex, Seznam) with every URL in
sitemap.xml so new/updated pages get crawled within minutes instead of
waiting on a scheduled crawl. Run after generate_pages.py + generate_home.py
so sitemap.xml is fresh. No account needed — the key file at the site root
is the only proof of ownership IndexNow requires.

Google does not support IndexNow; it must be reached via Search Console
(submit the sitemap there once, manually, after verifying ownership).
"""
import re
import json
import urllib.request

SITE_URL = "https://daily.mapt.cloud"
INDEXNOW_KEY = "6f764af03d2542fd8e80365fee476196"
ENDPOINT = "https://api.indexnow.org/indexnow"


def main():
    with open("sitemap.xml", encoding="utf-8") as f:
        xml = f.read()
    urls = re.findall(r"<loc>(.*?)</loc>", xml)
    if not urls:
        print("[indexnow] no urls found in sitemap.xml, skipping")
        return

    payload = json.dumps({
        "host": SITE_URL.replace("https://", "").replace("http://", ""),
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": urls,
    }).encode("utf-8")

    req = urllib.request.Request(
        ENDPOINT, data=payload, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"[indexnow] submitted {len(urls)} urls, status={resp.status}")
    except urllib.error.HTTPError as e:
        print(f"[indexnow] failed: {e.code} {e.read().decode(errors='ignore')}")
    except Exception as e:
        print(f"[indexnow] failed: {e}")


if __name__ == "__main__":
    main()
