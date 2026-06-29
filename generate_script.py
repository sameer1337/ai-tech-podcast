"""
Step 2 — Use Claude to write a natural podcast script from the top stories.
"""

from groq import Groq
from datetime import datetime
from config import GROQ_API_KEY, PODCAST_TITLE, EPISODE_TARGET_WORDS


CLIENT = Groq(api_key=GROQ_API_KEY)


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
- Open with a punchy hook, NOT "Welcome back" or "Hello listeners"
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
        model="llama-3.3-70b-versatile",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    script = message.choices[0].message.content.strip()
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
- Open with a punchy hook — do NOT start with "Welcome back" or "Hello listeners"
- Cover each story in 1-2 paragraphs — explain WHY it matters
- Use conversational language
- Add brief transitions between stories
- Close with a one-sentence teaser and sign-off
- Do NOT include stage directions, brackets, or URLs — pure spoken text only

Today's top stories:
{stories_block}

Write the script now:"""

    message = CLIENT.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    script = message.choices[0].message.content.strip()
    print(f"[script] Generated {len(script.split())} words for {niche['title']}")
    return script


if __name__ == "__main__":
    from fetch_news import fetch_stories
    stories = fetch_stories()
    script = generate_script(stories)
    print("\n" + "="*60)
    print(script)
