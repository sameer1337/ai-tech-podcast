# Social Auto-Poster + Distribution — setup

`auto_poster.py` publishes each day's issue to the channels you configure. Every
channel is independent: add its credentials (as **GitHub Secrets** for CI, or
local env vars) and it turns on automatically next run. Add none and it's inert.

**ToS-safe:** it posts only to YOUR OWN pages via official APIs. X/Twitter,
Reddit, and personal LinkedIn are intentionally NOT automated (that gets accounts
banned) — those stay copy-paste from `newsletter/TODAY.md`.

Test anytime without posting:
```bash
python auto_poster.py --dry              # show what would go out
python auto_poster.py --only telegram    # post to one channel
```

Ranked easiest → hardest to set up:

## 1. Telegram  (5 min, easiest, free)
1. In Telegram, message **@BotFather** → `/newbot` → get the **bot token**.
2. Create a public channel, add your bot as an **admin**.
3. Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` (e.g. `@aitechdaily`).

## 2. Bluesky  (5 min, free)
1. Settings → **App Passwords** → create one (not your main password).
2. Secrets: `BLUESKY_HANDLE` (e.g. `aitechdaily.bsky.social`), `BLUESKY_APP_PASSWORD`.

## 3. Dev.to  (5 min — this one earns you BACKLINKS)
1. dev.to → Settings → **Extensions** → generate a **DEV Community API Key**.
2. Secret: `DEVTO_API_KEY`.
Republishes the day's brief with a `canonical_url` back to daily.mapt.cloud →
a dofollow-style backlink + new readers, no duplicate-content penalty.

## 4. Facebook Page  (15 min — Meta app needed)
1. Create a **Facebook Page**.
2. developers.facebook.com → create an app → get a **Page access token**
   (long-lived) with `pages_manage_posts`.
3. Secrets: `FB_PAGE_ID`, `FB_PAGE_TOKEN`.

## 5. Instagram Business  (20 min — needs the FB app + an image)
1. Convert IG to a **Business/Creator** account and link it to your FB Page.
2. From the same Meta app, get the **IG user ID** + token with
   `instagram_content_publish`.
3. Secrets: `IG_USER_ID`, `IG_TOKEN`. Optionally `IG_IMAGE_URL` (defaults to your
   cover image — IG feed posts require an image).

---

### About "Boost" (paid ads)
Boosting = spending money via Meta Ads. Not automated here on purpose: it needs
your budget and per-campaign approval, and boosting newsletter signups to a cold
audience usually wastes money early. Grow with free organic + swaps first; revisit
paid once the funnel converts and there's revenue to reinvest.

### Other backlink channels (mostly manual)
- Republish to **Hashnode** / **Medium** with canonical (Medium stopped issuing
  API tokens, so it's manual now).
- **Newsletter directories**: InboxReads, Newsletter Stash, beehiiv discovery.
- **Product Hunt** + AI-tool directories (see the directory-submissions playbook).
- **Reddit / Quora / IndieHackers** — value-first, manual only.
