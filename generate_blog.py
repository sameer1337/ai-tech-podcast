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

    prompt = f"""You are a senior journalist writing an in-depth feature for "{niche['title']}", a publication covering {niche['hook']}.
Write a long, original, well-structured news article based on today's stories below.

Requirements:
- AT LEAST 1100 words of ORIGINAL prose — this is a long feature, do NOT be brief. Depth and analysis, not a rewrite of headlines.
- Open with a compelling 2-3 sentence introduction (no <h2>) that frames the day's biggest development and why readers should care.
- Then ONE <h2> section per major story. Each section MUST have 3-4 full paragraphs that explain what happened, the background/context a reader needs, why it matters, and what likely happens next. Where a story is thin, add a short paragraph of widely-known background context (clearly framed as context, never fabricated specifics).
- Include a final <h2>The bottom line</h2> section that ties the stories together, followed by a <ul> of 3-5 concrete key takeaways (<li>).
- Neutral, factual, journalistic tone. Attribute each fact to its source publication by name.
- Do NOT invent facts, quotes, statistics, or names not present in the summaries. Where a summary is thin, add general context a knowledgeable reader would expect — clearly framed as context, not fabricated specifics.
- Use <strong> for key terms and short paragraphs (2-4 sentences) for readability.

Return ONLY a JSON object with these exact keys:
  "title": an SEO headline (max 65 chars, keyword-first, no publication name)
  "dek": a one-sentence standfirst/subtitle (max 140 chars)
  "meta_description": a search snippet (max 155 chars)
  "body_html": the article body using ONLY <h2>, <p>, <ul>, <li>, <strong>, <a> tags
  "tags": array of 4-6 lowercase topic tags
  "image_query": 2-3 comma-separated simple, concrete visual keywords for a stock photo of the lead story (e.g. "bitcoin, trading, screen" or "hospital, doctor, research")

Today's stories (sources: {sources}):
{stories_block}
"""

    resp = CLIENT.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=4096,
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
        "image_query":      (data.get("image_query") or "").strip()[:60],
    }
    # Resolve a relevant lead image (Openverse, keyworded LoremFlickr fallback)
    try:
        from fetch_image import fetch_image
        seed = abs(hash(article["title"])) % 9973
        article["image_url"] = fetch_image(article["image_query"] or article["title"], seed, 900, 520)
    except Exception as e:
        article["image_url"] = ""
        print(f"[blog] image resolve failed: {e}")
    words = len(re.sub(r"<[^>]+>", " ", article["body_html"]).split())
    print(f"[blog] Article for {niche['title']}: {words} words, {len(article['tags'])} tags, img={'yes' if article['image_url'] else 'no'}")
    return article


def expand_script_to_article(script: str, niche: dict, fallback_title: str = "") -> dict:
    """Backfill path: turn an existing 5-min podcast SCRIPT into a long-form article.
    Same JSON contract + resolved image as generate_article."""
    prompt = f"""Below is the script of a short daily news briefing from "{niche['title']}" ({niche['hook']}).
Rewrite and EXPAND it into a long, original, well-structured news article.

Requirements:
- AT LEAST 1100 words — this is a long feature, do NOT be brief. Add background context and analysis; do NOT invent specific facts, names, quotes or numbers beyond the script.
- Compelling 2-3 sentence intro (no <h2>), then ONE <h2> per major story with 3-4 full paragraphs each (what happened, the background/context a reader needs, why it matters, and what's likely next). Where a story is thin, add a short "Context" paragraph of widely-known background.
- End with <h2>The bottom line</h2> and a <ul> of 3-5 key takeaways.
- Neutral, journalistic tone; short paragraphs; <strong> for key terms.

Return ONLY a JSON object with keys: "title" (<=65 chars, keyword-first, no publication name),
"dek" (<=140), "meta_description" (<=155), "body_html" (only <h2>,<p>,<ul>,<li>,<strong>,<a>),
"tags" (4-6 lowercase), "image_query" (2-3 comma-separated concrete visual keywords for the lead story).

Script:
{script[:4000]}
"""
    resp = CLIENT.chat.completions.create(
        model="llama-3.3-70b-versatile", max_tokens=4096, temperature=0.6,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    raw = _ALLOWED_FENCE.sub("", resp.choices[0].message.content.strip())
    data = json.loads(raw)
    article = {
        "title":            (data.get("title") or fallback_title or niche["title"]).strip()[:75],
        "dek":              (data.get("dek") or "").strip()[:160],
        "meta_description": (data.get("meta_description") or data.get("dek") or "").strip()[:160],
        "body_html":        _sanitize_html(data.get("body_html") or ""),
        "tags":             [str(t).lower().strip() for t in (data.get("tags") or [])][:6],
        "image_query":      (data.get("image_query") or "").strip()[:60],
    }
    try:
        from fetch_image import fetch_image
        seed = abs(hash(article["title"])) % 9973
        article["image_url"] = fetch_image(article["image_query"] or article["title"], seed, 900, 520)
    except Exception:
        article["image_url"] = ""
    words = len(re.sub(r"<[^>]+>", " ", article["body_html"]).split())
    print(f"[backfill] {niche['title']}: {words} words, img={'yes' if article['image_url'] else 'no'}")
    return article


if __name__ == "__main__":
    from fetch_news import fetch_stories_for_niche
    from niches import PODCAST_MAP
    n = PODCAST_MAP["ai-tech"]
    arts = generate_article(fetch_stories_for_niche(n), n)
    print(json.dumps(arts, indent=2)[:1200])
