"""
Step 2 — Use Claude to write a natural podcast script from the top stories.
"""

from groq import Groq
from datetime import datetime
from config import GROQ_API_KEY, PODCAST_TITLE, EPISODE_TARGET_WORDS, GROQ_MODEL


CLIENT = Groq(api_key=GROQ_API_KEY)

_WEAK_OPENERS = (
    "welcome", "hello", "hi ", "hey", "in today", "today we", "today, we",
    "the world of", "imagine", "in the past", "it's no secret", "picture this",
    "buckle up", "in this episode", "in a world",
)


def _strip_weak_opener(script: str) -> str:
    """If the script still opens with wind-up filler, drop that first sentence
    so the real news lands first. Cheap insurance against the model ignoring the
    hook instruction."""
    body = script.lstrip()
    first, sep, rest = body.partition(". ")
    if sep and rest.strip() and first.lower().lstrip("\"'").startswith(_WEAK_OPENERS):
        print("[script] Stripped weak opener:", first[:60])
        return rest.lstrip()
    return script


def generate_script(stories: list[dict]) -> str:
    today = datetime.now().strftime("%A, %B %d, %Y")
    episode_num_hint = datetime.now().strftime("%Y%m%d")

    stories_block = "\n\n".join(
        f"Story {i}: {s['title']}\nSource: {s['source']}\nURL: {s['url']}\nSummary: {s['summary'][:600]}"
        for i, s in enumerate(stories, 1)
    )

    prompt = f"""You are the host of "{PODCAST_TITLE}", a daily 5-minute AI and tech podcast.
Today is {today}.

Write a complete, natural-sounding podcast script for today's episode using the stories below.

Rules:
- Target {EPISODE_TARGET_WORDS} words (roughly 5 minutes at normal speaking pace)
- THE FIRST SENTENCE IS EVERYTHING. Lead with the single most surprising, specific
  fact from today's top story — a number, a name, or a concrete stakes statement.
  The listener must feel "wait, what?" within the first 8 words.
- BANNED openers — never begin with any of these or anything like them:
  "Welcome", "Hello", "Hi", "In today's episode", "Today we're", "The world of",
  "Imagine a world", "In the past", "It's no secret", "Picture this", "Buckle up".
  No scene-setting wind-up. Start mid-action, with the news itself.
  GOOD: "OpenAI just lost its three top safety researchers in a single week."
  BAD:  "The AI revolution is in full swing, but a dark cloud is looming..."
- Cover each story in 1-2 short paragraphs — explain WHY it matters, not just what happened
- Use conversational language; avoid jargon without a quick explanation
- Add brief transitions between stories ("Meanwhile...", "Shifting gears...", "On the AI front...")
- Close with one sentence teaser for tomorrow and a sign-off
- Do NOT include stage directions, sound cues, or brackets like [MUSIC] — pure spoken text only
- Do NOT mention URLs

Today's top stories:
{stories_block}

Write the script now:"""

    message = CLIENT.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    script = _strip_weak_opener(message.choices[0].message.content.strip())
    word_count = len(script.split())
    print(f"[script] Generated {word_count} words")
    return script


def generate_script_for_niche(stories: list[dict], niche: dict) -> str:
    """Generate a script for a specific niche."""
    today = datetime.now().strftime("%A, %B %d, %Y")
    stories_block = "\n\n".join(
        f"Story {i}: {s['title']}\nSource: {s['source']}\nSummary: {s['summary'][:600]}"
        for i, s in enumerate(stories, 1)
    )
    prompt = f"""You are the host of "{niche['title']}", a daily 5-minute podcast about {niche['hook']}.
Today is {today}.

Write a complete, natural-sounding podcast script using the stories below.

Rules:
- Target {EPISODE_TARGET_WORDS} words (roughly 5 minutes)
- THE FIRST SENTENCE IS EVERYTHING. Lead with the single most surprising, specific
  fact from today's top story — a number, a name, or a concrete stakes statement.
  The listener must feel "wait, what?" within the first 8 words.
- BANNED openers — never begin with any of these or anything like them:
  "Welcome", "Hello", "Hi", "In today's episode", "Today we're", "The world of",
  "Imagine a world", "In the past", "It's no secret", "Picture this", "Buckle up".
  No scene-setting wind-up. Start mid-action, with the news itself.
  GOOD example: "OpenAI just lost its three top safety researchers in a single week."
  BAD example:  "The AI revolution is in full swing, but a dark cloud is looming..."
- Cover each story in 1-2 paragraphs — explain WHY it matters
- Use conversational language
- Add brief transitions between stories
- Close with a one-sentence teaser and sign-off
- Do NOT include stage directions, brackets, or URLs — pure spoken text only

Today's top stories:
{stories_block}

Write the script now:"""

    message = CLIENT.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    script = _strip_weak_opener(message.choices[0].message.content.strip())
    print(f"[script] Generated {len(script.split())} words for {niche['title']}")
    return script


if __name__ == "__main__":
    from fetch_news import fetch_stories
    stories = fetch_stories()
    script = generate_script(stories)
    print("\n" + "="*60)
    print(script)
