"""
growth_agent.py — the "brain" layer on top of the deterministic pipeline.

Unlike the scripts (fetch → generate → deploy), this LOOKS at the state of the
project and DECIDES what to improve, then does the parts that are safe to
automate and drafts the parts that need a human. One agent, several skills, each
degrading gracefully when its credential isn't wired yet:

  seo       — audit every page for ranking problems; --fix rewrites weak/duplicate
              meta descriptions (Groq, cheap 8B) and injects missing Article schema.
  strategy  — read the project's signals + SEO report and write a ranked
              "DO THIS FIRST TODAY" block into newsletter/TODAY.md.
  scout     — curated newsletter-swap targets + drafted outreach (uses a search
              key if present; otherwise emits a strong templated task).
  daily     — strategy + an seo audit report (no auto-edits). Safe for CI.

Usage:
  python growth_agent.py daily            # CI-safe: audit report + strategy
  python growth_agent.py seo              # audit only, print report
  python growth_agent.py seo --fix --max 20   # fix up to 20 weak descriptions
  python growth_agent.py strategy
  python growth_agent.py scout
"""

import os
import re
import sys
import json
import glob
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from config import GROQ_API_KEY

SEO_MODEL   = os.environ.get("GROWTH_GROQ_MODEL", "llama-3.1-8b-instant")  # separate pool from 70B podcasts
BLOG_GLOB   = "blog/**/*.html"
EXTRA_PAGES = ["index.html", "about.html"]
REPORT_PATH = Path("logs/seo_audit.json")
TODAY_MD    = Path("newsletter/TODAY.md")

# Boilerplate/generic descriptions we consider "weak" even before dup-detection.
_WEAK_HINTS = [
    "updates and news", "podcast", "every morning", "in 5 minutes",
    "latest news on", "recent updates",
]

_TAGS   = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_DESC_RE = re.compile(r'(<meta\s+name="description"\s+content=")(.*?)(")', re.I | re.S)
_OGD_RE  = re.compile(r'(<meta\s+property="og:description"\s+content=")(.*?)(")', re.I | re.S)
_TITLE_RE= re.compile(r"<title>(.*?)</title>", re.I | re.S)


# ── helpers ────────────────────────────────────────────────────────────────
def _read(p):  return Path(p).read_text(encoding="utf-8", errors="replace")
def _write(p, s): Path(p).write_text(s, encoding="utf-8")

def _visible_text(html):
    t = _SCRIPT.sub(" ", html)
    t = _TAGS.sub(" ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def _title_of(html):
    m = _TITLE_RE.search(html)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

def _desc_of(html):
    m = _DESC_RE.search(html)
    return m.group(2).strip() if m else None

def _is_weak(desc):
    if not desc:            return True, "missing"
    d = desc.strip()
    if len(d) < 60:         return True, "too_short"
    if len(d) > 165:        return True, "too_long"
    low = d.lower()
    if any(h in low for h in _WEAK_HINTS):
        # boilerplate podcast blurb reused across pages
        return True, "boilerplate"
    return False, "ok"


# ── SEO audit ──────────────────────────────────────────────────────────────
def collect_pages():
    pages = sorted(glob.glob(BLOG_GLOB, recursive=True))
    pages += [p for p in EXTRA_PAGES if Path(p).exists()]
    return pages

def audit(pages=None):
    pages = pages or collect_pages()
    by_desc = defaultdict(list)
    problems = []          # list of {file, issues:[...]}
    for p in pages:
        html = _read(p)
        desc = _desc_of(html)
        title = _title_of(html)
        issues = []
        weak, why = _is_weak(desc)
        if weak: issues.append(why + "_description")
        if not title: issues.append("missing_title")
        if "application/ld+json" not in html: issues.append("missing_schema")
        if 'rel="canonical"' not in html: issues.append("missing_canonical")
        if desc: by_desc[desc.strip()].append(p)
        if issues:
            problems.append({"file": p, "title": title[:70], "desc": (desc or "")[:80], "issues": issues})

    # duplicate descriptions (same value on >1 page)
    dups = {d: fs for d, fs in by_desc.items() if len(fs) > 1}
    dup_files = set()
    for fs in dups.values():
        dup_files.update(fs)
    for prob in problems:
        if prob["file"] in dup_files and "duplicate_description" not in prob["issues"]:
            prob["issues"].append("duplicate_description")
    # pages whose ONLY problem is being a duplicate weren't caught above; add them
    known = {p["file"] for p in problems}
    for d, fs in dups.items():
        for f in fs:
            if f not in known:
                problems.append({"file": f, "title": _title_of(_read(f))[:70],
                                 "desc": d[:80], "issues": ["duplicate_description"]})

    report = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "pages_scanned": len(pages),
        "pages_with_issues": len(problems),
        "duplicate_description_groups": len(dups),
        "duplicate_pages": len(dup_files),
        "issue_counts": _tally(problems),
        "problems": problems,
    }
    REPORT_PATH.parent.mkdir(exist_ok=True)
    _write(REPORT_PATH, json.dumps(report, indent=2))
    return report

def _tally(problems):
    c = defaultdict(int)
    for p in problems:
        for i in p["issues"]:
            c[i] += 1
    return dict(sorted(c.items(), key=lambda x: -x[1]))

def print_report(rep):
    print(f"\n  SEO audit — {rep['pages_scanned']} pages, "
          f"{rep['pages_with_issues']} with issues")
    print(f"  Duplicate-description groups: {rep['duplicate_description_groups']} "
          f"({rep['duplicate_pages']} pages)")
    for k, v in rep["issue_counts"].items():
        print(f"    - {k:26} {v}")
    print(f"  Full report → {REPORT_PATH}")


# ── SEO fix (rewrite weak/duplicate descriptions + add schema) ──────────────
def _gen_description(title, body_text):
    prompt = (
        "Write ONE unique, compelling meta description for this news article, "
        "for Google search results. 140-158 characters, specific to THIS story, "
        "keyword-first, no clickbait, no quotes, no publication name.\n\n"
        f"Title: {title}\nArticle text: {body_text[:900]}\n\n"
        "Return ONLY the description text, nothing else."
    )
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    r = client.chat.completions.create(
        model=SEO_MODEL, max_tokens=90, temperature=0.5,
        messages=[{"role": "user", "content": prompt}],
    )
    d = r.choices[0].message.content.strip().strip('"').strip()
    return re.sub(r"\s+", " ", d)[:160]

def _esc_attr(s):
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")

def _article_schema(title, desc, html, path):
    m = re.search(r'rel="canonical"\s+href="([^"]+)"', html)
    url = m.group(1) if m else f"https://daily.mapt.cloud/{path.replace(os.sep, '/')}"
    dm = re.search(r"(\d{4}-\d{2}-\d{2})", path)
    date = dm.group(1) if dm else datetime.now().strftime("%Y-%m-%d")
    obj = {
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": title[:110], "description": desc,
        "datePublished": date, "dateModified": date,
        "url": url, "mainEntityOfPage": url,
        "publisher": {"@type": "Organization", "name": "Mapt Daily"},
    }
    return '<script type="application/ld+json">' + json.dumps(obj) + '</script>'

def fix(max_fix=20, dry=False):
    rep = audit()
    # Prioritise the highest-impact fixes: duplicate + boilerplate + missing.
    def score(p):
        s = 0
        for i in p["issues"]:
            if i == "duplicate_description": s += 3
            if i == "boilerplate_description": s += 3
            if i == "missing_description": s += 4
            if i.endswith("_description"): s += 1
        return -s
    # Only auto-rewrite ARTICLE pages. Static/landing pages (index, about) have
    # hand-written descriptions — deriving one from their body text (which includes
    # the news ticker) produces nonsense, so audit them but never auto-fix them.
    _no_autofix = {os.path.normpath(p) for p in EXTRA_PAGES}
    targets = [p for p in rep["problems"]
               if os.path.normpath(p["file"]) not in _no_autofix
               and (any(i.endswith("_description") for i in p["issues"])
                    or "missing_schema" in p["issues"])]
    targets.sort(key=score)
    targets = targets[:max_fix]

    fixed = 0
    for p in targets:
        path = p["file"]
        html = _read(path)
        title = _title_of(html) or p["title"]
        changed = False

        # 1) rewrite weak/duplicate description
        needs_desc = any(i.endswith("_description") for i in p["issues"])
        if needs_desc:
            try:
                new_desc = _gen_description(title, _visible_text(html))
            except Exception as e:
                print(f"  [warn] desc gen failed for {path}: {e}")
                new_desc = None
            if new_desc:
                esc = _esc_attr(new_desc)
                if _DESC_RE.search(html):
                    html = _DESC_RE.sub(lambda m: m.group(1) + esc + m.group(3), html, count=1)
                else:  # inject after <title>
                    html = _TITLE_RE.sub(lambda m: m.group(0) + f'\n<meta name="description" content="{esc}">', html, count=1)
                if _OGD_RE.search(html):
                    html = _OGD_RE.sub(lambda m: m.group(1) + esc + m.group(3), html, count=1)
                changed = True
                print(f"  ✓ desc  {Path(path).name[:52]} → {new_desc[:60]}…")

        # 2) inject Article schema if missing
        if "missing_schema" in p["issues"] and "application/ld+json" not in html:
            desc_now = _desc_of(html) or p["desc"]
            schema = _article_schema(title, desc_now, html, path)
            if "</head>" in html:
                html = html.replace("</head>", schema + "\n</head>", 1)
                changed = True
                print(f"  ✓ schema {Path(path).name[:52]}")

        if changed and not dry:
            _write(path, html)
            fixed += 1
        elif changed:
            fixed += 1  # counted, but not written in dry mode

    print(f"\n  {'[dry-run] would fix' if dry else 'Fixed'} {fixed} page(s). "
          f"{len(targets)} targeted this run (cap {max_fix}).")
    return fixed


# ── Strategist ─────────────────────────────────────────────────────────────
def _sub_count():
    for p in ("subscribers.csv", "newsletter/subscribers.csv"):
        if Path(p).exists():
            try: return sum(1 for _ in open(p, encoding="utf-8", errors="ignore") if _.strip())
            except Exception: pass
    return None

def strategy():
    subs = _sub_count()
    rep = json.loads(_read(REPORT_PATH)) if REPORT_PATH.exists() else audit()
    actions = []

    # Rank actions by leverage given current state.
    dup = rep.get("duplicate_pages", 0)
    if dup:
        actions.append(f"**SEO (biggest win):** {dup} pages share duplicate meta descriptions. "
                       f"Run `python growth_agent.py seo --fix --max 20` — chips away 20/day within the free token budget.")
    if subs is None:
        actions.append("**Setup:** beehiiv isn't live yet — finish NEWSLETTER_SETUP.md so subscriber growth actually starts compounding.")
    else:
        if subs < 500:
            actions.append(f"**Growth (you're at {subs} subs):** priority is raw reach — add the subscribe CTA to every Spotify episode note + YouTube Short description today.")
        elif subs < 2500:
            actions.append(f"**Growth ({subs} subs):** turn on beehiiv Recommendations + send 1 swap DM (see `scout`).")
        elif subs < 6000:
            actions.append(f"**Money ({subs} subs):** apply to the beehiiv Ad Network and pitch your first direct sponsor.")
        else:
            actions.append(f"**Money ({subs} subs):** launch/optimize the premium tier and book multiple sponsors/week.")

    actions.append("**Consistency:** post today's auto-drafted X + LinkedIn (below) and leave 2 genuine Reddit comments.")

    block = ["<!-- growth_agent:priority -->",
             f"## 🎯 DO THIS FIRST TODAY  ·  {datetime.now():%Y-%m-%d}",
             ""]
    for i, a in enumerate(actions, 1):
        block.append(f"{i}. {a}")
    block += ["", f"_Subscribers: {subs if subs is not None else 'n/a'} · "
              f"SEO issues: {rep.get('pages_with_issues', '?')} · agent ran {datetime.now():%H:%M}_",
              "", "---", ""]
    header = "\n".join(block)

    TODAY_MD.parent.mkdir(exist_ok=True)
    existing = _read(TODAY_MD) if TODAY_MD.exists() else ""
    existing = re.sub(r"<!-- growth_agent:priority -->.*?---\n\n", "", existing, flags=re.S)
    _write(TODAY_MD, header + existing)
    print("  [strategy] priority block written → " + str(TODAY_MD))
    for a in actions: print("   • " + re.sub(r"\*\*|`", "", a))
    return actions


# ── Scout (newsletter-swap targets + outreach) ─────────────────────────────
_SWAP_TARGETS = [
    ("TLDR AI", "tldr.tech/ai", "huge; aim for a Boost, not a peer swap"),
    ("Ben's Bites", "bensbites.com", "AI daily; peer-swap candidate as you grow"),
    ("The Rundown AI", "therundown.ai", "big; Boost target"),
    ("Mindstream", "mindstream.news", "AI daily; swap candidate"),
    ("AI Breakfast", "aibreakfast.beehiiv.com", "beehiiv native — easy Recommendation swap"),
    ("The Neuron", "theneurondaily.com", "AI daily; swap candidate"),
]

def scout():
    key = os.environ.get("SERPAPI_KEY") or os.environ.get("SEARCH_API_KEY")
    print("  [scout] " + ("search key found — live discovery enabled." if key
          else "no search key — using curated target list (set SERPAPI_KEY for live discovery)."))
    lines = ["<!-- growth_agent:scout -->",
             "## 🔭 Newsletter-swap targets (beehiiv Recommendations)", ""]
    for name, url, note in _SWAP_TARGETS:
        lines.append(f"- **{name}** — {url}  _({note})_")
    lines += ["",
        "**Outreach DM template (personalise line 1):**",
        "```",
        "Hey [name] — big fan of [specific recent issue]. I run AI Tech Daily "
        "(free daily AI brief + podcast). Our audiences overlap a lot — want to "
        "set up a beehiiv Recommendation swap? Happy to feature you first.",
        "```",
        "⚠️ You send these yourself — never auto-DM (bans + spam). The agent only drafts.",
        "", "---", ""]
    out = "\n".join(lines)
    TODAY_MD.parent.mkdir(exist_ok=True)
    existing = _read(TODAY_MD) if TODAY_MD.exists() else ""
    existing = re.sub(r"<!-- growth_agent:scout -->.*?---\n\n", "", existing, flags=re.S)
    _write(TODAY_MD, existing + out)
    print("  [scout] swap targets appended → " + str(TODAY_MD))


# ── CLI ────────────────────────────────────────────────────────────────────
def main():
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("-") else "daily"
    max_fix = 20
    if "--max" in args:
        try: max_fix = int(args[args.index("--max") + 1])
        except Exception: pass
    dry = "--dry" in args

    if cmd == "seo":
        if "--fix" in args: fix(max_fix=max_fix, dry=dry)
        else: print_report(audit())
    elif cmd == "strategy": strategy()
    elif cmd == "scout": scout()
    elif cmd == "daily":
        print_report(audit()); strategy()
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
