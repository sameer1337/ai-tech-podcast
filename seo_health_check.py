"""Technical SEO health sweep across all 3 Mapt-family sites + Telegram digest.

Self-contained (this repo's own copy of the same logic used in the seo-agent
repo's shared/seo_health.py) since this is a separate git repo/CI checkout —
uses httpx rather than requests to match this repo's existing dependency set.
Read-only / report-only: flags problems, does not attempt to auto-fix them.
"""
import argparse
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

UA = "Mozilla/5.0 (compatible; seo-agent-healthcheck/1.0)"
TIMEOUT = 12
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

SITES = {
    "daily.mapt.cloud": "https://daily.mapt.cloud/sitemap.xml",
    "rovexlube.com": "https://rovexlube.com/sitemap.xml",
    "mapt.cloud": "https://mapt.cloud/sitemap.xml",
}


def fetch_sitemap_urls(client: httpx.Client, sitemap_url: str, max_urls: int = 200) -> list:
    resp = client.get(sitemap_url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    locs = [el.text.strip() for el in root.iter(f"{SITEMAP_NS}loc") if el.text]
    if root.tag.endswith("sitemapindex"):
        urls = []
        for sub in locs[:5]:
            try:
                urls.extend(fetch_sitemap_urls(client, sub, max_urls=max_urls))
            except Exception:
                continue
        return urls[:max_urls]
    return locs[:max_urls]


def check_link(client: httpx.Client, url: str) -> dict:
    start = time.time()
    try:
        resp = client.head(url, headers={"User-Agent": UA}, timeout=TIMEOUT, follow_redirects=True)
        if resp.status_code >= 400 or resp.status_code == 405:
            resp = client.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError as exc:
        return {"url": url, "ok": False, "error": str(exc)}
    elapsed_ms = round((time.time() - start) * 1000)
    return {"url": url, "ok": resp.status_code < 400, "status": resp.status_code, "ms": elapsed_ms}


def check_onpage_basics(client: httpx.Client, url: str) -> dict:
    try:
        resp = client.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        resp.raise_for_status()
        html = resp.text
    except httpx.HTTPError as exc:
        return {"url": url, "error": str(exc)}

    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    meta_desc = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.IGNORECASE
    )
    h1_count = len(re.findall(r"<h1[\s>]", html, re.IGNORECASE))

    issues = []
    if not title or not title.group(1).strip():
        issues.append("missing_title")
    if not meta_desc or not meta_desc.group(1).strip():
        issues.append("missing_meta_description")
    if h1_count == 0:
        issues.append("missing_h1")
    elif h1_count > 1:
        issues.append(f"multiple_h1({h1_count})")

    return {"url": url, "issues": issues}


def run_health_check(link_sample: int = 40, onpage_sample: int = 8) -> dict:
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "sites": {}}
    with httpx.Client() as client:
        for name, sitemap_url in SITES.items():
            site_report = {"sitemap": sitemap_url}
            try:
                urls = fetch_sitemap_urls(client, sitemap_url)
            except Exception as exc:
                site_report["error"] = f"sitemap fetch failed: {exc}"
                report["sites"][name] = site_report
                continue

            site_report["url_count"] = len(urls)
            sample = urls[:link_sample]
            link_results = [check_link(client, u) for u in sample]
            broken = [r for r in link_results if not r.get("ok")]
            slow = [r for r in link_results if r.get("ms", 0) > 3000]

            onpage_results = [check_onpage_basics(client, u) for u in sample[:onpage_sample]]
            onpage_problems = [r for r in onpage_results if r.get("issues") or r.get("error")]

            site_report["links_checked"] = len(link_results)
            site_report["broken_links"] = broken
            site_report["slow_links"] = slow
            site_report["onpage_checked"] = len(onpage_results)
            site_report["onpage_problems"] = onpage_problems
            report["sites"][name] = site_report

    return report


def summarize(report: dict) -> str:
    lines = []
    for name, site in report["sites"].items():
        if "error" in site:
            lines.append(f"{name}: ERROR — {site['error']}")
            continue
        broken = len(site.get("broken_links", []))
        slow = len(site.get("slow_links", []))
        onpage = len(site.get("onpage_problems", []))
        status = "OK" if (broken == 0 and onpage == 0) else "ISSUES"
        lines.append(
            f"{name}: {status} — {site['url_count']} URLs, "
            f"{broken} broken / {slow} slow (of {site['links_checked']}), "
            f"{onpage} on-page issues (of {site['onpage_checked']})"
        )
    return "\n".join(lines)


def send_telegram(message: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID")
    if not token or not chat_id:
        print("[notify] TELEGRAM_BOT_TOKEN/TELEGRAM_CHANNEL_ID not set, skipping")
        return False
    resp = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"[notify] Telegram send failed: {resp.status_code} {resp.text}")
        return False
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="logs/seo_health_report.json")
    parser.add_argument("--notify", action="store_true", help="Also send a Telegram digest")
    args = parser.parse_args()

    result = run_health_check()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    summary = summarize(result)
    print(summary)

    if args.notify:
        send_telegram(f"SEO health check {datetime.now(timezone.utc).date()}\n\n{summary}")
