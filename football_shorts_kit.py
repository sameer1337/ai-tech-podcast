# -*- coding: utf-8 -*-
"""
Daily football Shorts production kit — one command, 5-10 ready-to-make Shorts.

Pulls REAL match data (ESPN's free scoreboard API, no key) plus Google News
context, then generates for every Short: a 45-55s script with time beats,
6 Veo prompts (8s clips each), YouTube title, description, and hashtags.

IMPORTANT — footage: broadcast highlight clips are rights-held (FIFA/leagues
Content-ID claim or strike them fast). This kit's method is the legal one that
already worked on the channel: REAL facts and scores in the voiceover, with
AI-generated (Veo) cinematic recreations as visuals — generic players by kit
color, never real player likenesses or federation crests.

Output: shorts_kits/football_<YYYY-MM-DD>.md

Usage:
  python football_shorts_kit.py                       # 8 mixed shorts (news + matches)
  python football_shorts_kit.py --mode news           # only drama shorts (bans/injuries/red cards)
  python football_shorts_kit.py --mode matches        # only match recaps/previews
  python football_shorts_kit.py --length punchy       # force all ~20-30s (best retention)
  python football_shorts_kit.py --length full         # force all ~45-55s
  python football_shorts_kit.py --count 10 --leagues fifa.world,eng.1

--mode default: mixed (news short first — it's the channel's top-performing format).
--length default: auto (news/live = punchy ~25s, recap/preview = full ~50s).
"""
import os, re, sys, json, time, urllib.request
from datetime import datetime, timedelta

from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL

CLIENT  = Groq(api_key=GROQ_API_KEY)
# Short scripts don't need the 70B model, and its free tier is only 100K tokens/day
# (shared with the podcast + blog pipeline). The 8B-instant model has a much larger
# daily budget and is plenty for Shorts — so a 10-short kit never starves the pipeline.
KIT_MODEL = os.environ.get("FOOTBALL_MODEL",
             next((sys.argv[sys.argv.index("--model") + 1] for a in sys.argv if a == "--model"),
                  "llama-3.1-8b-instant"))
COUNT   = int(next((sys.argv[sys.argv.index("--count") + 1]
                    for a in sys.argv if a == "--count"), 8))
LEAGUES = next((sys.argv[sys.argv.index("--leagues") + 1]
                for a in sys.argv if a == "--leagues"), "fifa.world").split(",")
# mode:   mixed (news + matches, default) | news (drama only) | matches (games only)
# length: auto (news=punchy ~25s, recap=full ~50s) | punchy | full
MODE   = next((sys.argv[sys.argv.index("--mode")   + 1] for a in sys.argv if a == "--mode"),   "mixed").lower()
LENGTH = next((sys.argv[sys.argv.index("--length") + 1] for a in sys.argv if a == "--length"), "auto").lower()

LEAGUE_NAMES = {
    "fifa.world":     "FIFA World Cup 2026",
    "uefa.champions": "UEFA Champions League",
    "eng.1":          "Premier League",
    "esp.1":          "La Liga",
    "ita.1":          "Serie A",
    "ger.1":          "Bundesliga",
    "fra.1":          "Ligue 1",
}

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fetch_matches(league: str) -> list[dict]:
    """Yesterday + today + tomorrow scoreboard for one league."""
    matches = []
    for off in (-1, 0, 1):
        day = (datetime.now() + timedelta(days=off)).strftime("%Y%m%d")
        url = (f"https://site.api.espn.com/apis/site/v2/sports/soccer/"
               f"{league}/scoreboard?dates={day}")
        try:
            data = _get_json(url)
        except Exception as e:
            print(f"[matches] {league} {day}: fetch failed ({e})")
            continue
        for e in data.get("events", []):
            comp = (e.get("competitions") or [{}])[0]
            teams = {t.get("homeAway"): t for t in comp.get("competitors", [])}
            home, away = teams.get("home", {}), teams.get("away", {})
            state = ((e.get("status") or {}).get("type") or {})
            goals = []
            for d in comp.get("details", []):
                ttext = (d.get("type") or {}).get("text", "")
                if "Goal" not in ttext:
                    continue
                who = ", ".join(a.get("athlete", {}).get("displayName", "")
                                for a in d.get("athletesInvolved", []) if a.get("athlete"))
                goals.append(f"{ttext} at {d.get('clock',{}).get('displayValue','?')}"
                             + (f" ({who})" if who.strip(", ") else ""))
            notes = "; ".join(n.get("headline", "") for n in comp.get("notes", []) if n.get("headline"))
            matches.append({
                "league":  LEAGUE_NAMES.get(league, league),
                "name":    e.get("name", ""),
                "when":    e.get("date", ""),
                "state":   state.get("state", ""),          # pre / in / post
                "status":  state.get("description", ""),
                "round":   notes,
                "home":    home.get("team", {}).get("displayName", "?"),
                "away":    away.get("team", {}).get("displayName", "?"),
                "score":   f"{home.get('score','')}-{away.get('score','')}".strip("-"),
                "venue":   (comp.get("venue") or {}).get("fullName", ""),
                "goals":   goals,
            })
    return matches


def _news(query: str, n: int = 4) -> list[str]:
    try:
        from fetch_news import _google_news_search
        return [f"{s['title']} — {s['source']}" for s in _google_news_search(query, n)]
    except Exception:
        return []


# Drama angles that made the channel's top short (a red-card ban at 94% retention).
DRAMA_QUERIES = [
    "{c} injury ruled out", "{c} suspension ban", "{c} red card",
    "{c} starting lineup XI", "{c} penalty VAR controversy",
    "{c} shock result upset", "{c} manager sacked reaction",
]


def _norm(t: str) -> frozenset:
    return frozenset(w for w in re.sub(r"[^a-z0-9 ]", " ", t.lower()).split() if len(w) > 3)


def fetch_storylines(comp: str, want: int) -> list[dict]:
    """Distinct football NEWS/drama headlines for the competition. Each becomes a
    single-storyline short (the highest-retention format on the channel)."""
    from fetch_news import _google_news_search
    out, seen = [], []
    queries = [q.format(c=comp) for q in DRAMA_QUERIES] + [comp]
    for q in queries:
        if len(out) >= want:
            break
        try:
            for s in _google_news_search(q, 3):
                title = s.get("title", "").strip()
                toks = _norm(title)
                if len(toks) < 4 or any(len(toks & prev) / max(len(toks), 1) > 0.5 for prev in seen):
                    continue
                seen.append(toks)
                related = [n for n in _google_news_search(title, 3)[1:] if n.get("title")]
                out.append({
                    "headline": title,
                    "source":   s.get("source", ""),
                    "context":  "; ".join(n["title"] for n in related),
                })
                if len(out) >= want:
                    break
        except Exception as e:
            print(f"[news] '{q}' failed: {e}")
    return out


# Length presets — data says short news shorts retain best (a 0:23 news short
# hit 94% avg-view). punchy for drama, full for recaps.
LENGTH_SPEC = {
    "punchy": (55,  75, "20-30 seconds"),
    "full":   (130, 150, "45-55 seconds"),
}


def _length_for(kind: str) -> str:
    if LENGTH in ("punchy", "full"):
        return LENGTH
    # auto: news/drama + live = punchy (highest retention); recap/preview = full
    return "punchy" if ("NEWS" in kind or "LIVE" in kind) else "full"


# Visual guidance differs: match shorts show play; news shorts show the moment
# (a red card, a dejected player, medics, an empty seat) — still generic, no faces.
VISUALS_MATCH = ("players in colored kits battling for the ball, crowds, stadium "
                 "exteriors, the ball hitting the net, scoreboard-style graphics, trophy glints")
VISUALS_NEWS  = ("a referee holding up a red card, a lone player in a colored kit sitting "
                 "dejected on the bench with head down, medical staff attending on the pitch, "
                 "an empty stadium seat under a spotlight, a tunnel, close-up of boots on grass, "
                 "a tactics board, dramatic stadium exterior at dusk")


def short_rules(kind: str) -> str:
    length = _length_for(kind)
    lo, hi, secs = LENGTH_SPEC[length]
    is_news = "NEWS" in kind
    visuals = VISUALS_NEWS if is_news else VISUALS_MATCH
    news_note = ("""
- This is a NEWS/DRAMA short about ONE storyline (a ban, injury, red card, lineup
  call, or controversy). CRITICAL ACCURACY RULE: use ONLY facts explicitly written
  in the headline and coverage below. Invent NOTHING — no motives, no politicians,
  no clubs, no stats, no streaks, no scores, no quotes that are not written there.
  If the coverage is thin, keep the script short rather than inventing filler. Do
  not speculate beyond a cautious "reports say" for anything the headline implies.
  The hook = the single real consequence in the headline (e.g. "He'll MISS the semi-final").
  You MAY use the real player/manager/team NAME from the headline in the title and
  spoken script — but the VEO PROMPTS must stay generic (kit colour only, no real
  faces/names/logos).""" if is_news else "")
    return f"""
Rules for the Short (non-negotiable):
- Total length ~{secs}. The "script" MUST be {lo}-{hi} words of natural spoken prose
  (this exact length is REQUIRED). No on-screen timestamps in the script text — just
  flowing narration that starts with the hook and ends with the CTA line
  ("Follow for daily World Cup recaps" or similar).
- The hook must create an information gap in the FIRST 3 SECONDS — a shock fact,
  score tease, or "nobody saw this coming" framing. Never open with "welcome" or a plain match name.{news_note}
- Voiceover carries ALL real facts. NEVER invent scorers, stats, minutes, quotes, or
  names not present in the facts below. Where unknown, describe it generically.
- "veo_prompts": exactly 6 prompts, each ONE ~8-second 9:16 VERTICAL cinematic clip.
  Use visuals like: {visuals}. CRITICAL: no real player names or faces, no
  federation/club crests or logos — teams referred to ONLY by kit color. Add
  "no text, no logos" to EVERY prompt.
- "title": max 85 chars, front-load the shock/teams, end with #Shorts.
- "description": 2-3 sentences + a hashtags line.
- "hashtags": 5-7 tags like #WorldCup2026.

Return ONLY a JSON object: {{"title","hook","script","veo_prompts":[6 strings],"description","hashtags":[...],"tags":[...]}}
"""


def gen_short(kind: str, facts: str, news: list[str]) -> dict:
    length = _length_for(kind)
    lo, hi, _ = LENGTH_SPEC[length]
    ctx = ("\nRelated headlines / coverage:\n" + "\n".join(f"- {h}" for h in news)) if news else ""
    prompt = f"""You write viral YouTube Shorts scripts for a football (soccer) channel.
Create ONE {kind} Short from these REAL facts.
{short_rules(kind)}
Facts:
{facts}{ctx}
"""
    messages = [{"role": "user", "content": prompt}]
    data = None
    # News shorts run cooler to curb fabrication; recaps a bit warmer for flair.
    temp = 0.35 if "NEWS" in kind else 0.7
    # Groq undershoots length; retry until the SCRIPT lands in range (accept a
    # little slack so we don't loop forever on a stubborn model).
    for attempt in range(3):
        resp = CLIENT.chat.completions.create(
            model=KIT_MODEL, max_tokens=2048, temperature=temp,
            response_format={"type": "json_object"},
            messages=messages,
        )
        raw = _FENCE.sub("", resp.choices[0].message.content.strip())
        data = json.loads(raw)
        wc = len((data.get("script") or "").split())
        if lo - 8 <= wc <= hi + 25:
            break
        print(f"[kit]   script {wc} words (want {lo}-{hi}) — rewriting ({attempt+1})")
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content":
            f"The \"script\" was {wc} words; it MUST be {lo}-{hi} words — "
            f"{'expand with more real detail, stakes and momentum' if wc < lo else 'tighten it'}. "
            "Return the FULL JSON object again with the same keys, only the script length fixed."})
    data["_length"] = length
    return data


def render_md(shorts: list[dict], date: str) -> str:
    secs = {"punchy": "20-30s", "full": "45-55s"}
    out = [f"# Football Shorts Kit — {date}",
           f"\n{len(shorts)} Shorts | Veo (8s clips, 9:16) + CapCut assembly",
           "\n## Production checklist (every Short)",
           "- 9:16 vertical only; keep to the length noted per short",
           "- Generate the 6 Veo clips, import to CapCut in order",
           "- AI voiceover reading the script (own voiceover = full revenue share)",
           "- Captions in the MIDDLE zone (avoid top 20% / bottom 25% UI)",
           "- Do NOT use broadcast/TV footage — Content ID will claim or strike it",
           "- Fastest path: `python assemble_football_short.py --clips-dir <folder> "
           "--hook \"<HOOK>\" --script @script.txt --out x.mp4`",
           "\n---\n"]
    for i, s in enumerate(shorts, 1):
        out.append(f"\n## SHORT {i}: {s.get('title','')}")
        out.append(f"**Type:** {s.get('_kind','')} | **Target length:** "
                   f"{secs.get(s.get('_length','full'),'45-55s')} | **Topic:** {s.get('_label','')}\n")
        if s.get("_source"):
            flag = "⚠️ VERIFY the script matches this before uploading — " if "NEWS" in s.get("_kind","") else ""
            out.append(f"**Source:** {flag}{s['_source']}\n")
        out.append("### Script\n```\n" + s.get("script", "") + "\n```\n")
        out.append("### Veo prompts (6 clips)")
        for j, p in enumerate(s.get("veo_prompts", []), 1):
            out.append(f"\n**Clip {j}:**\n```\n{p}\n```")
        out.append("\n### Upload metadata")
        out.append(f"**Title:** {s.get('title','')}")
        out.append(f"\n**Description:**\n{s.get('description','')}")
        out.append(f"\n**Hashtags:** {' '.join(s.get('hashtags', []))}")
        out.append(f"\n**Tags:** {', '.join(s.get('tags', []))}")
        out.append("\n---")
    return "\n".join(out)


def build_match_items() -> list:
    """(kind, label, facts, news_query) for each real fixture."""
    items = []
    for lg in LEAGUES:
        for m in fetch_matches(lg):
            label = f"{m['home']} vs {m['away']}"
            base = (f"Competition: {m['league']}" + (f" ({m['round']})" if m['round'] else "") +
                    f"\nMatch: {label}\nVenue: {m['venue']}\nStatus: {m['status']}")
            if m["state"] == "post":
                facts = base + f"\nFINAL SCORE: {m['home']} {m['score']} {m['away']}"
                if m["goals"]:
                    facts += "\nGoal events: " + "; ".join(m["goals"])
                src = f"ESPN final: {m['home']} {m['score']} {m['away']}"
                items.append(("match RECAP", label, facts, f"{m['home']} vs {m['away']} {m['league']}", src))
            elif m["state"] == "pre":
                facts = base + f"\nKickoff (UTC): {m['when']}"
                items.append(("match PREVIEW (build hype, ask viewers to predict the score in comments)",
                              label, facts, f"{m['home']} vs {m['away']} preview", "ESPN fixture (upcoming)"))
            else:
                facts = base + f"\nLIVE right now, current score: {m['home']} {m['score']} {m['away']}"
                items.append(("LIVE-match hype", label, facts, f"{m['home']} vs {m['away']}",
                              f"ESPN live: {m['home']} {m['score']} {m['away']}"))
    return items


def build_news_items(want: int) -> list:
    """(kind, label, facts, news_query, source) for each drama storyline."""
    comp = LEAGUE_NAMES.get(LEAGUES[0], LEAGUES[0])
    items = []
    for st in fetch_storylines(comp, want):
        facts = (f"Competition: {comp}\nStoryline headline: {st['headline']} ({st['source']})"
                 + (f"\nRelated: {st['context']}" if st["context"] else ""))
        src = f"{st['headline']} — {st['source']}"
        items.append(("football NEWS/drama", st["headline"][:60], facts, "", src))
    return items


def _interleave(a: list, b: list, n: int) -> list:
    """Alternate two lists (news first — it's the top performer), cap at n."""
    out, i = [], 0
    while len(out) < n and (i < len(a) or i < len(b)):
        if i < len(a):
            out.append(a[i])
        if len(out) < n and i < len(b):
            out.append(b[i])
        i += 1
    return out[:n]


def main():
    date = datetime.now().strftime("%Y-%m-%d")

    if MODE == "news":
        items = build_news_items(COUNT)
    elif MODE == "matches":
        items = build_match_items()[:COUNT]
    else:  # mixed — news first (highest retention), then alternate with matches
        matches = build_match_items()
        news = build_news_items(max(COUNT - len(matches), (COUNT + 1) // 2) + 2)
        items = _interleave(news, matches, COUNT)
        if len(items) < COUNT:                       # top up from whatever's left
            extra = [x for x in (news + matches) if x not in items]
            items += extra[:COUNT - len(items)]

    if not items:
        print("[kit] no matches or storylines found — try --leagues or check connectivity"); return

    print(f"[kit] mode={MODE} length={LENGTH} model={KIT_MODEL} — generating {len(items)} shorts")
    shorts = []
    for kind, label, facts, q, src in items:
        news = _news(q, 4) if q else []
        try:
            s = gen_short(kind, facts, news)
            s["_kind"], s["_label"], s["_source"] = kind, label, src
            shorts.append(s)
            tag = "NEWS" if "NEWS" in kind else "MATCH"
            print(f"[kit] {len(shorts)}/{len(items)} [{tag}/{s.get('_length')}] {label[:40]}: {s.get('title','')[:60]}")
        except Exception as e:
            print(f"[kit] {label} ERROR: {e}")
        time.sleep(4)

    if not shorts:
        print("[kit] nothing generated"); return
    os.makedirs("shorts_kits", exist_ok=True)
    path = f"shorts_kits/football_{date}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_md(shorts, date))
    print(f"\nKit ready: {path}  ({len(shorts)} Shorts)")


if __name__ == "__main__":
    main()
