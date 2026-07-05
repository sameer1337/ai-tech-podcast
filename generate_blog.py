"""
Generate an expanded blog article from the same source stories used for the
podcast. This is the text layer that makes the site Google-indexable and
AdSense-eligible — longer and more detailed than the 5-minute audio script.

Output (per episode, saved by run_all): logs/<niche>/<date>_article.json
  { "title", "dek", "meta_description", "body_html", "tags" }

body_html uses a restricted tag set (<h2>,<p>,<ul>,<li>,<strong>,<a>) so it can
be dropped straight into a post template.
"""

import json
import re
from groq import Groq
from config import GROQ_API_KEY

CLIENT = Groq(api_key=GROQ_API_KEY)

_ALLOWED_FENCE = re.compile(r"^```(?:json|html)?\s*|\s*```$", re.IGNORECASE)


def _sanitize_html(html: str) -> str:
    """Strip anything we never want injected from an LLM into a page."""
    html = re.sub(r"<\s*(script|iframe|style|link|meta)[^>]*>.*?<\s*/\s*\1\s*>",
                  "", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<\s*(script|iframe|style|link|meta)[^>]*/?>", "", html, flags=re.IGNORECASE)
    return html.strip()


def generate_article(stories: list[dict], niche: dict) -> dict:
    sources = ", ".join(sorted({s.get("source", "") for s in stories if s.get("source")}))
    stories_block = "\n\n".join(
        f"Story {i}: {s['title']}\nSource: {s.get('source','')}\nSummary: {s['summary'][:700]}"
        for i, s in enumerate(stories, 1)
    )

    prompt = f"""You are a journalist writing for "{niche['title']}", a publication covering {niche['hook']}.
Write an original, well-structured blog article based on today's stories below.

Requirements:
- 700-1000 words of ORIGINAL prose — analyze and explain, don't just restate headlines.
- Open with a strong lede that states the most important development plainly.
- One <h2> section per major story; weave in why it matters and what happens next.
- Neutral, factual, journalistic tone. Attribute facts to their source by name.
- Do NOT invent facts, quotes, or numbers not present in the summaries.

Return ONLY a JSON object with these exact keys:
  "title": an SEO headline (max 65 chars, keyword-first, no publication name)
  "dek": a one-sentence standfirst/subtitle (max 140 chars)
  "meta_description": a search snippet (max 155 chars)
  "body_html": the article body using ONLY <h2>, <p>, <ul>, <li>, <strong>, <a> tags
  "tags": array of 4-6 lowercase topic tags

Today's stories (sources: {sources}):
{stories_block}
"""

    resp = CLIENT.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=2600,
        temperature=0.6,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )

    raw = _ALLOWED_FENCE.sub("", resp.choices[0].message.content.strip())
    data = json.loads(raw)

    # Normalize / guard
    article = {
        "title":            (data.get("title") or niche["title"]).strip()[:75],
        "dek":              (data.get("dek") or "").strip()[:160],
        "meta_description": (data.get("meta_description") or data.get("dek") or "").strip()[:160],
        "body_html":        _sanitize_html(data.get("body_html") or ""),
        "tags":             [str(t).lower().strip() for t in (data.get("tags") or [])][:6],
    }
    words = len(re.sub(r"<[^>]+>", " ", article["body_html"]).split())
    print(f"[blog] Article for {niche['title']}: {words} words, {len(article['tags'])} tags")
    return article


if __name__ == "__main__":
    from fetch_news import fetch_stories_for_niche
    from niches import PODCAST_MAP
    n = PODCAST_MAP["ai-tech"]
    arts = generate_article(fetch_stories_for_niche(n), n)
    print(json.dumps(arts, indent=2)[:1200])
