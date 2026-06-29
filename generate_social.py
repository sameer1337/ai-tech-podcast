"""
Generate social media posts for each episode automatically.
Saves to logs/{niche}/{date}_social.txt for easy copy-paste.
"""

from groq import Groq
from config import GROQ_API_KEY

CLIENT = Groq(api_key=GROQ_API_KEY)

SOCIAL_SUBREDDITS = {
    "ai-tech":    ["r/artificial", "r/MachineLearning", "r/technology"],
    "finance":    ["r/investing", "r/personalfinance", "r/stocks"],
    "health":     ["r/longevity", "r/nutrition", "r/Health"],
    "startup":    ["r/startups", "r/entrepreneur", "r/venturecapital"],
    "crypto":     ["r/CryptoCurrency", "r/Bitcoin", "r/ethereum"],
    "world-news": ["r/worldnews", "r/geopolitics", "r/news"],
    "true-crime": ["r/TrueCrime", "r/UnresolvedMysteries", "r/crime"],
}


def generate_social_posts(niche: dict, episode_title: str, script: str) -> dict:
    pid = niche["id"]
    subreddits = SOCIAL_SUBREDDITS.get(pid, [])

    prompt = f"""You are a social media manager for "{niche['title']}", a daily podcast.

Episode title: {episode_title}
Script excerpt: {script[:800]}

Generate ALL of the following in one response:

TWEET (under 240 chars, no hashtags in text, punchy, make people want to listen):
[tweet text here]

HASHTAGS (8 relevant hashtags for this niche, space separated):
[hashtags here]

REDDIT_TITLE (compelling Reddit post title, under 100 chars, no clickbait):
[reddit title here]

REDDIT_BODY (2-3 sentence Reddit post body, conversational, mention it's a free podcast):
[reddit body here]

LINKEDIN (professional 3-sentence post about today's episode insight):
[linkedin text here]

Write exactly in the format above with the labels."""

    msg = CLIENT.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.choices[0].message.content.strip()

    # Parse sections
    def extract(label, text):
        try:
            start = text.index(label) + len(label)
            end   = text.index("\n\n", start) if "\n\n" in text[start:] else len(text)
            return text[start:end].strip()
        except ValueError:
            return ""

    tweet     = extract("TWEET\n", raw + "\n\n")
    hashtags  = extract("HASHTAGS\n", raw + "\n\n")
    r_title   = extract("REDDIT_TITLE\n", raw + "\n\n")
    r_body    = extract("REDDIT_BODY\n", raw + "\n\n")
    linkedin  = extract("LINKEDIN\n", raw + "\n\n")

    website_url = f"https://sameer1337.github.io/ai-tech-podcast"

    output = f"""=== {niche['title']} — {episode_title} ===

--- TWITTER/X ---
{tweet}
{hashtags}
{website_url}

--- REDDIT (post in {', '.join(subreddits)}) ---
Title: {r_title}

{r_body}

Listen free: {website_url}

--- LINKEDIN ---
{linkedin}

Listen free: {website_url}

"""
    return {"text": output, "tweet": tweet, "hashtags": hashtags,
            "reddit_title": r_title, "reddit_body": r_body, "linkedin": linkedin}
