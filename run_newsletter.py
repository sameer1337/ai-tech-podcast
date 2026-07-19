"""
Daily newsletter orchestrator + ops pack.

Runs AFTER the podcast/blog pipeline (or standalone). Each morning it:
  1. Fetches today's AI stories (shared with the podcast — zero extra content cost)
  2. Builds the email + archive page + appends to newsletter.xml (beehiiv auto-sends)
  3. Auto-drafts today's growth posts (X / LinkedIn / Reddit) with your subscribe link
  4. Writes newsletter/TODAY.md — your one-glance "do this now" sheet with the drafts

The only manual work left is ~15 min of pasting the auto-written posts +
replying to comments. Everything above is automated.

Usage:
  python run_newsletter.py            # full daily run
  python run_newsletter.py --test     # print, write nothing
  python run_newsletter.py --no-social  # skip the ops pack (newsletter only)
"""

import os
import re
import sys
import json
from datetime import datetime
from pathlib import Path

from config import GROQ_API_KEY, GROQ_MODEL
import generate_newsletter as nl

SUBREDDITS = ["r/artificial", "r/technology", "r/OpenAI", "r/MachineLearning"]
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def build_ops_pack(brief: dict, date_str: str) -> dict:
    """Auto-draft the day's growth posts from the same brief. Free (Groq)."""
    top = brief["items"][0] if brief.get("items") else {"headline": "today's AI news", "blurb": ""}
    headlines = "; ".join(it["headline"] for it in brief.get("items", [])[:5])
    archive_url = f"{nl.NEWS_BASE}/{date_str}.html"
    sub_url = nl.BEEHIIV_SUB_URL

    prompt = f"""You run growth for "{nl.BRAND}", a free daily AI newsletter ({nl.TAGLINE}).
Today's top story: {top['headline']} — {top.get('blurb','')}
All headlines today: {headlines}

Write ready-to-post copy. Return ONLY JSON with these keys:
  "tweet": under 260 chars, hook + 1 insight, ends with a soft CTA. No hashtags inside the sentence.
  "hashtags": 5 relevant hashtags, space separated (e.g. "#AI #tech ...").
  "linkedin": 3-4 short sentences, professional, one concrete takeaway from today, ends inviting people to subscribe free.
  "reddit_title": under 90 chars, genuine and specific to the top story, NOT promotional, no "check out my newsletter".
  "reddit_comment": 3-4 sentences of genuine value/analysis a person would post in a thread about this story; may end with a single soft mention that you write a free daily brief. Never spammy.
Do not invent facts beyond the story text. Return ONLY the JSON."""

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=nl.NL_MODEL, max_tokens=700, temperature=0.7,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(_FENCE.sub("", resp.choices[0].message.content.strip()))
    except Exception as e:
        print(f"  [warn] ops pack Groq failed ({e}); using minimal drafts.")
        data = {
            "tweet": f"{top['headline']}. Full 5-min AI brief today 👇 {sub_url}",
            "hashtags": "#AI #tech #artificialintelligence #startups #news",
            "linkedin": f"{top['headline']}. {top.get('blurb','')} I break down the day's AI news in a free 5-minute email — subscribe: {sub_url}",
            "reddit_title": top["headline"],
            "reddit_comment": top.get("blurb", ""),
        }

    data["archive_url"] = archive_url
    data["sub_url"] = sub_url
    return data


def write_today_md(brief: dict, ops: dict, date_str: str) -> Path:
    nl.NEWS_DIR.mkdir(exist_ok=True)
    tweet = ops.get("tweet", "")
    tags = ops.get("hashtags", "")
    md = f"""# ☀️ AI Tech Daily — TODAY ({date_str})

**Newsletter status:** ✅ auto-generated & queued (beehiiv sends from RSS).
**Subject line going out:** {brief.get('subject','')}
**Archive / share link:** {ops.get('archive_url','')}

Everything above happened automatically. Below is your ~15-minute manual growth block.
Paste each post, then log numbers in the dashboard.

---

## 1) Post to X / Twitter  (2 min)
```
{tweet}

{tags}
```
Then: reply to your own tweet with the archive link: {ops.get('archive_url','')}

## 2) Post to LinkedIn  (2 min)
```
{ops.get('linkedin','')}
```

## 3) Reddit — value-first comment  (5 min)
Find/scan a live thread about today's top story in one of: {", ".join(SUBREDDITS)}
**Suggested post title (only if starting a thread):** {ops.get('reddit_title','')}
```
{ops.get('reddit_comment','')}
```
⚠️ Reddit rule: give value first. Only mention the newsletter once, softly, if it fits.

## 4) Engage  (5 min)
- Reply to every comment/DM from yesterday.
- Answer 2 AI questions on r/artificial or Hacker News (link only in your profile).

## 5) Growth op of the day  (5 min — pick ONE)
- [ ] Send 1 beehiiv Recommendation swap DM to another AI newsletter
- [ ] Pitch 1 sponsor / affiliate (from month 3+)
- [ ] Add newsletter CTA to one more surface (a Spotify episode note, a YouTube short description)

## 6) Log metrics  (1 min)
Open the dashboard → enter yesterday's: new subscribers, open %, click %.

---
*Generated by run_newsletter.py. Re-run any morning to refresh.*
"""
    out = nl.NEWS_DIR / "TODAY.md"
    out.write_text(md, encoding="utf-8")
    return out


def main():
    try:  # Windows consoles default to cp1252 and choke on emoji in --test output
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    test = "--test" in sys.argv
    do_social = "--no-social" not in sys.argv
    date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*56}\n  {nl.BRAND} newsletter — {date_str}\n{'='*56}")
    stories = nl._load_today_stories()
    if not stories:
        print("ERROR: no stories fetched."); sys.exit(1)

    brief = nl.generate(stories, date_str, test=test)

    if do_social:
        print(">> Drafting today's growth posts...")
        ops = build_ops_pack(brief, date_str)
        if test:
            print(f"\n[X]     {ops.get('tweet','')}")
            print(f"[TAGS]  {ops.get('hashtags','')}")
            print(f"[LI]    {ops.get('linkedin','')}")
            print(f"[RDT-T] {ops.get('reddit_title','')}")
            print(f"[RDT-C] {ops.get('reddit_comment','')}")
        else:
            out = write_today_md(brief, ops, date_str)
            print(f"  [ops] today's action sheet → {out}")

    print("\nDone. beehiiv will send from newsletter.xml on its next RSS check.")


if __name__ == "__main__":
    main()
