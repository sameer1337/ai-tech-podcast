"""
Generate the daily YouTube Community post for the Velox Daily channel.

One post per day, type decided by weekday:
  Mon  opinion poll        Tue  trivia quiz         Wed  image post (episode promo)
  Thu  topic-picker poll   Fri  news quiz (from this week's stories)
  Sat  image poll          Sun  video clip caption

Saves to logs/community/{date}_community.txt for copy-paste into YouTube Studio.
YouTube has NO API for Community posts, so the posting step itself stays manual
(~60 seconds/day). Wed/Sat also generate a matching image via Pollinations.

Usage: python generate_community.py            # today's post
       python generate_community.py 2026-07-10 # specific date (for testing)
"""

import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

OUT_DIR = Path("logs/community")

# ── Static content banks (rotate weekly, safe fallback if LLM fails) ────────

POLLS = [  # Monday — opinion polls, zero-knowledge, comment bait
    {"q": "Which AI do you *actually* use most?",
     "opts": ["ChatGPT", "Claude", "Gemini", "Other (comment it 👇)"]},
    {"q": "Will AI change your job in the next 5 years?",
     "opts": ["Yes, massively", "A little", "Not at all", "It already did"]},
    {"q": "Hot take: AI-generated content should be labeled by law. Defend your vote in the comments 👇",
     "opts": ["Agree", "Disagree"]},
    {"q": "Would you ride in a driverless taxi today?",
     "opts": ["Absolutely", "Never", "Only if it's free 😅"]},
    {"q": "Which Big Tech company do you trust most with your data?",
     "opts": ["Google", "Apple", "Microsoft", "None of them 💀"]},
    {"q": "How do you get your tech news?",
     "opts": ["YouTube", "Podcasts", "Twitter/X", "Doomscrolling at 2am"]},
    {"q": "Perfect length for a daily news podcast?",
     "opts": ["5 min", "10 min", "20+ min", "Depends on the news"]},
    {"q": "Smart glasses: the next smartphone, or the next 3D TV?",
     "opts": ["Next smartphone", "Next 3D TV", "Too early to tell"]},
]

QUIZZES = [  # Tuesday — evergreen trivia, correct answer first (shuffle when pasting)
    {"q": "What does \"GPT\" actually stand for?",
     "correct": "Generative Pre-trained Transformer",
     "wrong": ["General Purpose Technology", "Guided Prompt Text", "Global Processing Tool"],
     "explain": "Generative Pre-trained Transformer — the architecture behind the modern AI boom."},
    {"q": "Which voice assistant launched FIRST?",
     "correct": "Siri (2011)",
     "wrong": ["Alexa (2014)", "Google Assistant (2016)", "Cortana (2014)"],
     "explain": "Siri shipped with the iPhone 4S in October 2011, three years before Alexa."},
    {"q": "The 2017 research paper that kicked off the modern AI boom is called…",
     "correct": "\"Attention Is All You Need\"",
     "wrong": ["\"Deep Thinking\"", "\"The Transformer Effect\"", "\"Neural Networks 2.0\""],
     "explain": "Google's 2017 paper introduced the Transformer — the T in GPT."},
    {"q": "The world's first computer \"bug\" was…",
     "correct": "An actual moth stuck in the machine",
     "wrong": ["A coding typo", "A power failure", "A prank by engineers"],
     "explain": "A real moth, found in Harvard's Mark II computer in 1947 and taped into the logbook."},
    {"q": "Roughly how many emails are sent worldwide EVERY DAY?",
     "correct": "~350 billion",
     "wrong": ["~1 billion", "~20 billion", "~5 trillion"],
     "explain": "Around 350 billion emails move every single day — most of it automated."},
    {"q": "Which country has the most data centers?",
     "correct": "USA",
     "wrong": ["China", "Germany", "India"],
     "explain": "The US hosts more data centers than the next several countries combined."},
    {"q": "Roughly what share of all internet traffic comes from bots, not humans?",
     "correct": "About half",
     "wrong": ["About 5%", "About 15%", "Almost none"],
     "explain": "Roughly half of all internet traffic is bots — crawlers, scrapers, and AI agents."},
    {"q": "What was the first video ever uploaded to YouTube about?",
     "correct": "A trip to the zoo",
     "wrong": ["A music video", "A tech review", "A cat"],
     "explain": "\"Me at the zoo\", 19 seconds, April 2005. Now there are billions of videos."},
]

TOPIC_PICKER_FALLBACK = [  # Thursday fallback if LLM unavailable
    {"q": "What should this week's deep-dive be? 👇",
     "opts": ["AI agents taking over work", "Chip war: US vs China",
              "Where crypto is headed", "The next iPhone moment"]},
    {"q": "Pick tomorrow's episode focus:",
     "opts": ["Big Tech earnings", "New AI model drops",
              "Startup of the week", "Weirdest tech news"]},
    {"q": "Which topic do we cover WAY too little?",
     "opts": ["Robotics", "Space tech", "Cybersecurity", "Biotech + AI"]},
]

IMAGE_POLLS = [  # Saturday — each needs an attached image
    {"q": "Is this photo REAL or AI-generated? 🤔 (answer in tomorrow's post)",
     "opts": ["100% real", "That's AI"],
     "image_prompt": "photorealistic candid street photography, golden hour city scene "
                     "with people, shot on 35mm film, natural imperfections, no text"},
    {"q": "Which setup would you rather work on for a year?",
     "opts": ["Setup A (left)", "Setup B (right)"],
     "image_prompt": "split image two halves: left minimal white desk single laptop plant, "
                     "right triple monitor RGB gaming battlestation dark room, no text"},
    {"q": "Which 2000s gadget do you miss most?",
     "opts": ["iPod", "Flip phone", "Digital camera", "MP3 player"],
     "image_prompt": "nostalgic 2000s gadgets flat lay: ipod classic, flip phone, "
                     "compact digital camera, mp3 player, retro colors, no text"},
    {"q": "Real robot or CGI? 🤖",
     "opts": ["Real robot", "CGI / AI render"],
     "image_prompt": "photorealistic humanoid robot walking in a modern office lobby, "
                     "documentary photography style, natural lighting, no text"},
]

CHANNEL_PLUG = "We break down stories like this every morning in 5 minutes — Velox Daily. 🎧"

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def todays_stories(date_str: str, niche_id: str = "ai-tech") -> list:
    raw = _read(f"logs/{niche_id}/{date_str}_stories.txt")
    if not raw:  # fall back to the most recent day that has stories
        candidates = sorted(Path(f"logs/{niche_id}").glob("*_stories.txt"))
        if candidates:
            raw = _read(str(candidates[-1]))
    return [s.strip() for s in raw.split("||") if s.strip()]


def week_stories(date: datetime) -> list:
    """Headlines from the last 5 days across all niches (for the Friday quiz)."""
    from niches import PODCASTS
    stories = []
    for back in range(5):
        d = (date - timedelta(days=back)).strftime("%Y-%m-%d")
        for p in PODCASTS:
            for s in todays_stories(d, p["id"]):
                if s not in stories:
                    stories.append(s)
    return stories


def episode_link(date_str: str, niche_id: str = "ai-tech") -> str:
    """Today's episode if uploaded, else the latest one, else the channel page.
    (The community step runs before today's upload in the daily pipeline.)"""
    vid = _read(f"logs/{niche_id}/{date_str}_youtube.txt")
    if not vid:
        candidates = sorted(Path(f"logs/{niche_id}").glob("*_youtube.txt"))
        if candidates:
            vid = _read(str(candidates[-1]))
    return f"https://youtu.be/{vid}" if vid else "https://www.youtube.com/@veloxdaily"


def ask_llm(prompt: str, max_tokens: int = 300) -> str:
    """Groq call; returns '' on any failure so callers fall back to banks."""
    try:
        from groq import Groq
        from config import GROQ_API_KEY
        msg = Groq(api_key=GROQ_API_KEY).chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.choices[0].message.content.strip()
    except Exception as e:
        print(f"[community] LLM unavailable ({e}), using fallback bank")
        return ""


def generate_image(prompt: str, out_path: str) -> bool:
    """Pollinations image (same pattern as episode thumbnails)."""
    import time
    seed = abs(hash(prompt)) % 99999
    url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
           f"?width=1280&height=720&nologo=true&model=flux&seed={seed}")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "podcast-bot/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 5000:
                raise ValueError("image too small")
            with open(out_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"[community] image attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(8)
    return False


def _rotate(bank: list, date: datetime):
    return bank[date.isocalendar()[1] % len(bank)]


def _poll_block(q: str, opts: list) -> str:
    lines = "\n".join(f"  {i + 1}. {o}" for i, o in enumerate(opts))
    return f"[QUESTION — paste this]\n{q}\n\n[OPTIONS]\n{lines}"


def _quiz_block(quiz: dict, link: str) -> str:
    opts = "\n".join(f"  - {o}" for o in [quiz["correct"]] + quiz["wrong"])
    return (f"[QUESTION — paste this]\n{quiz['q']}\n\n"
            f"[OPTIONS — correct listed FIRST, shuffle the order when pasting]\n{opts}\n\n"
            f"[MARK CORRECT]\n  {quiz['correct']}\n\n"
            f"[EXPLANATION field — shows after answering, this is your free ad slot]\n"
            f"  {quiz['explain']} {CHANNEL_PLUG}\n  {link}")


# ── Per-weekday builders ─────────────────────────────────────────────────────

def build_monday(date):
    p = _rotate(POLLS, date)
    return "TEXT POLL (opinion)", _poll_block(p["q"], p["opts"]), None


def build_tuesday(date):
    link = episode_link(date.strftime("%Y-%m-%d"))
    q = _rotate(QUIZZES, date)
    return "QUIZ (trivia)", _quiz_block(q, link), None


def build_wednesday(date):
    date_str = date.strftime("%Y-%m-%d")
    stories = todays_stories(date_str)
    link = episode_link(date_str)
    top = stories[0] if stories else "today's top story"

    teaser = ask_llm(
        "Write ONE cliffhanger teaser line (max 18 words) for this news story. "
        "Create curiosity, don't spoil the outcome, no hashtags, no quotes around it.\n"
        f"Story: {top}") or f"{top} — and it changes more than you think."
    teaser = teaser.splitlines()[0].strip()

    text = (f"[TEXT — paste this]\n"
            f"⚡ Today in 5 minutes:\n{teaser}\n"
            f"Full breakdown 🎧 → {link}\n"
            f"What's your take? 👇")

    img_prompt = (f"bold tech news promo image, glowing AI circuit brain, deep blue purple, "
                  f"dramatic lighting, topic: {top[:80]}, no text, no words, cinematic")
    return "IMAGE POST (episode promo)", text, img_prompt


def build_thursday(date):
    headlines = week_stories(date)[:15]
    block = None
    if headlines:
        raw = ask_llm(
            "From these news headlines, write 4 SHORT poll options (3-6 words each) for a "
            "YouTube poll asking subscribers which topic a podcast should deep-dive next. "
            "Output ONLY the 4 options, one per line, no numbering, no intro.\n\n"
            + "\n".join(headlines))
        opts = [l.strip("-• ").strip() for l in raw.splitlines() if l.strip()][:4] if raw else []
        if len(opts) == 4:
            block = _poll_block("What should this week's deep-dive be? 👇", opts)
    if not block:
        p = _rotate(TOPIC_PICKER_FALLBACK, date)
        block = _poll_block(p["q"], p["opts"])
    return "TEXT POLL (topic picker)", block, None


def build_friday(date):
    date_str = date.strftime("%Y-%m-%d")
    link = episode_link(date_str)
    headlines = week_stories(date)[:20]
    if headlines:
        raw = ask_llm(
            "You write a weekly news quiz for a daily news podcast's YouTube community tab.\n"
            "From these real headlines from this week, create ONE multiple-choice question "
            "about the most notable story. Format EXACTLY:\n"
            "Q: <question>\nCORRECT: <right answer>\nWRONG: <wrong 1> | <wrong 2> | <wrong 3>\n"
            "EXPLAIN: <one-line answer explanation>\n\nHeadlines:\n" + "\n".join(headlines),
            max_tokens=250)
        try:
            lines = {l.split(":", 1)[0].strip(): l.split(":", 1)[1].strip()
                     for l in raw.splitlines() if ":" in l}
            quiz = {"q": "🧠 Were you paying attention this week?\n" + lines["Q"],
                    "correct": lines["CORRECT"],
                    "wrong": [w.strip() for w in lines["WRONG"].split("|")][:3],
                    "explain": lines["EXPLAIN"]}
            return "QUIZ (this week's news)", _quiz_block(quiz, link), None
        except (KeyError, IndexError):
            print("[community] Could not parse LLM quiz, using trivia bank")
    q = QUIZZES[(date.isocalendar()[1] + 4) % len(QUIZZES)]  # offset so it differs from Tuesday
    return "QUIZ (trivia fallback)", _quiz_block(q, link), None


def build_saturday(date):
    p = _rotate(IMAGE_POLLS, date)
    return "IMAGE POLL", _poll_block(p["q"], p["opts"]), p["image_prompt"]


def build_sunday(date):
    text = ("[CLIP] Pick the most surprising 30-60s moment from this week's episodes "
            "(vertical crop if possible), hard cut at the cliffhanger.\n\n"
            "[CAPTION — paste this]\n"
            "The story everyone missed this week 👀\n"
            "Full version + a new episode every morning. Which story should we go deeper on? 👇")
    return "VIDEO POST (clip of the week)", text, None


BUILDERS = [build_monday, build_tuesday, build_wednesday,
            build_thursday, build_friday, build_saturday, build_sunday]


# ── Entry point ──────────────────────────────────────────────────────────────

def write_community_post(date: datetime = None) -> str:
    date = date or datetime.now()
    date_str = date.strftime("%Y-%m-%d")
    day = date.weekday()

    post_type, body, image_prompt = BUILDERS[day](date)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image_note = ""
    if image_prompt:
        img_path = OUT_DIR / f"{date_str}_image.png"
        if img_path.exists() or generate_image(image_prompt, str(img_path)):
            image_note = f"[IMAGE — attach this file]\n  {img_path}\n\n"
        else:
            image_note = "[IMAGE] generation failed — attach any fitting image manually\n\n"

    content = (
        f"{'=' * 60}\n"
        f"VELOX DAILY — COMMUNITY POST — {DAY_NAMES[day]} {date_str}\n"
        f"Type   : {post_type}\n"
        f"Post at: 7:30-9:00 AM ET  (5:00-6:30 PM IST)\n"
        f"Where  : youtube.com → Create → Post  (or Studio → Content → Posts)\n"
        f"{'=' * 60}\n\n"
        f"{image_note}{body}\n\n"
        f"{'-' * 60}\n"
        f"After posting: reply to every comment in the first hour.\n"
    )

    out_path = OUT_DIR / f"{date_str}_community.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[community] {DAY_NAMES[day]} {post_type} saved -> {out_path}")
    return str(out_path)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    d = datetime.strptime(arg, "%Y-%m-%d") if arg else None
    write_community_post(d)
