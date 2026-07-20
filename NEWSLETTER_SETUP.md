# AI Tech Daily — Newsletter Setup (one-time, ~30 min)

The code is done and wired into CI. This is the manual half only **you** can do
(account creation, API keys). Do it once; then it runs itself every morning.

---

## What's already automated (no action needed)

| Piece | File | Runs |
|---|---|---|
| Fetch AI stories | `fetch_news.py` (shared with podcast) | daily 6am CI |
| Write email brief (subject, intro, 5 stories) | `generate_newsletter.py` | daily |
| Build HTML email + archive page | `generate_newsletter.py` → `newsletter/<date>.html` | daily |
| Append to send feed | `generate_newsletter.py` → `newsletter.xml` | daily |
| Draft your X / LinkedIn / Reddit posts | `run_newsletter.py` → `newsletter/TODAY.md` | daily |
| Deploy archive + feed to daily.mapt.cloud | `deploy_ftp.py` | daily |

Uses `llama-3.1-8b-instant` (separate free Groq quota from the 7 podcasts, so it
never competes for tokens). If Groq is ever down, a clean template fallback ships anyway.

---

## Step 1 — Create the beehiiv publication (10 min)

1. Sign up free at **https://beehiiv.com** (free tier: unlimited sends to 2,500 subs).
2. Create a publication: **AI Tech Daily**, tagline "The 5-minute AI brief you can also listen to."
3. Settings → **Publication ID** — copy it (looks like `pub_xxxxxxxx-xxxx-...`).
4. Settings → **API** → create an **API key** — copy it.
5. Grab your public subscribe URL (Settings → your `*.beehiiv.com` or custom domain).

### Publication IDs (recorded 2026-07-19)
- **API V2 (use this one):** `pub_d898927b-2405-4391-9836-a3aae47553d8` — already wired into `subscribe.php`
- API V1 (legacy): `d898927b-2405-4391-9836-a3aae47553d8`

> ⚠️ The **API key** is NOT stored here and must never be committed — this repo is
> public. Put it in an env var / GitHub Secret only. Creating one requires Stripe
> Identity verification, which is optional: the embed-form path below needs no API.

## Step 2 — Feed signups into beehiiv (5 min)

`subscribe.php` already forwards new signups to beehiiv. Just add credentials.
On Hostinger, either edit the two constants at the top of `subscribe.php`:

```php
$BEEHIIV_API_KEY = 'paste-key-here';
$BEEHIIV_PUB_ID  = 'pub_xxxxxxxx-...';
```

...or (better) set them as environment variables in Hostinger's PHP config.
Until filled, signups still save to `subscribers.csv` — nothing is lost.

**Import your existing list:** beehiiv → Subscribers → Import → upload `subscribers.csv`.

## Step 3 — Turn on automated sending from the RSS feed (10 min)

The daily email is published to `https://daily.mapt.cloud/newsletter.xml`.
In beehiiv, point an automation at it so each new issue sends itself:

- beehiiv → **Automations / RSS-to-Send** (a.k.a. "Auto-send from RSS") →
  add feed URL `https://daily.mapt.cloud/newsletter.xml` → send as soon as a new item appears.

> If your beehiiv plan doesn't expose RSS-to-send, fallback is 30 seconds/day:
> open `newsletter/latest.html`, copy it into a new beehiiv post, hit send. Or
> upgrade later — direct sponsors will more than cover it.

## Step 4 — Add the GitHub secret (2 min)

Repo → Settings → Secrets → Actions → add:

- `BEEHIIV_SUB_URL` = your beehiiv subscribe URL (used in post CTAs). Optional; falls back to `daily.mapt.cloud/#subscribe`.

`GROQ_API_KEY` and the `FTP_*` secrets already exist.

---

## Daily routine (after setup)

1. Morning: CI generates + deploys the newsletter and writes `newsletter/TODAY.md`. beehiiv sends it.
2. You: open the **dashboard**, do the ~15-min growth block (paste the pre-written posts from `TODAY.md`), log yesterday's numbers.

## Run it manually anytime

```bash
python run_newsletter.py            # generate + write today's issue and TODAY.md
python run_newsletter.py --test     # preview in terminal, write nothing
python run_newsletter.py --no-social # newsletter only, skip the post drafts
```

## Monetization switches (flip as you grow)

| Subs | Turn on |
|---|---|
| 0 | Affiliate links in the brief; beehiiv referral program |
| ~1,000 | Apply to beehiiv **Ad Network** (auto-fills the sponsor slot) |
| ~2,500+ | Upgrade beehiiv (paid) or stay free; launch **premium tier** |
| ~6,000+ | Pitch **direct sponsors** — the `{{SPONSOR}}` slot + "Book this slot" mailto is already in the template |
