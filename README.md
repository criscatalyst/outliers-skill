# Outliers — Claude Code skill

Cross-niche YouTube outlier detection + personalized title variant generation.

Finds videos that **massively over-performed their channel's average** (5x, 10x, 20x normal views), filters out your own niche so you only see what's working *next door*, and generates 3 title variants per outlier — adapted to your niche, your ICP, your voice.

## What it does

1. Runs the YouTube Data API v3 against a list of search terms (default: creator economy, personal brand, content creation, digital products, solopreneur, side hustle — or pass your own).
2. For each video found, computes **outlier score** = `video views ÷ channel median views`. A 5x outlier = the video did 5 times the channel's normal performance.
3. Filters out your own niche (so you don't recycle your own bubble).
4. Reads your `~/CLAUDE.md` to learn your niche / ICP / voice.
5. Generates 3 title variants per outlier — adapted to YOUR niche, keeping the same psychological hook the original used.
6. Optionally pushes the results to Mission Control as content ideas.

## Why "cross-niche"

If you only watch your own niche, you only see the same patterns recycled. Outliers from adjacent niches expose hooks you wouldn't have thought of — but you can adapt. A finance hook structure works in fitness. A fitness hook structure works in productivity. The skill is the cross-pollination.

## Install

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/criscatalyst/outliers-skill.git ~/.claude/skills/outliers
cd ~/.claude/skills/outliers
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and fill in your `YOUTUBE_API_KEY`.

## Get a YouTube API key (free, 5 min)

1. Go to https://console.cloud.google.com
2. Create a project (or use existing)
3. APIs & Services → Library → search **YouTube Data API v3** → Enable
4. APIs & Services → Credentials → Create credentials → API key
5. Copy the key into `.env` as `YOUTUBE_API_KEY=...`

Free tier: **10,000 quota units / day**. A default run uses ~600 units, so you can run ~16 hunts per day at zero cost.

### Optional: Apify token (for transcripts)

If you want hook breakdowns based on the actual video transcript (not just titles), grab a free token at https://apify.com and add it as `APIFY_API_TOKEN=...` in `.env`. Without it, the skill still works — just no transcript-based summaries.

## Usage

In Claude Code:

> find outliers

> outliers in fitness

> outliers --queries 1

> /outliers personal finance for women

The skill runs the detector, parses results, and presents each outlier with hook analysis + 3 title variants in your voice.

### Options

- `--queries N` — number of keywords from the default list to use (default: all 6)
- `--terms "X" "Y"` — custom search terms instead of defaults
- `--min_score N` — minimum outlier multiplier (default: 5)
- `--limit N` — top N outliers per query (default: 10)
- `--skip_transcripts` — faster, skips transcript fetching (default: enabled in the skill)

## Output format

For each outlier:

```
**#3 — "I Quit My $200K Job. Biggest Mistake Of My Life." (12x outlier)**
@JohnDoe | 2.4M views | 14 days old | Career

Hook analysis: Pattern interrupt + regret reveal. Loss aversion drives the click —
"biggest mistake" pulls people in to find out what went wrong, even if they have
no plans to quit their job.

Title variants:
1. "I Built My Personal Brand To 100K. Biggest Mistake Of My Life."
2. "I Sold My First Digital Product For $50K. Biggest Mistake Of My Life."
3. "I Quit Posting To Build A Course. Biggest Mistake Of My Life."
```

## Personalization

The skill reads your `~/CLAUDE.md` (specifically the Voice rules, Anti-slop rules, and Offer & goals sections) to know:

- Your niche → so variants are in your space, not generic
- Your ICP → so variants speak to YOUR audience
- Your voice rules → so variants don't use words you've banned
- Your offer → so variants align with what you sell

If you haven't run [`anti-slop-interview`](https://github.com/criscatalyst/anti-slop-interview-skill) yet, the outliers skill will ask you for niche + ICP one-liner before generating variants. Better to set up CLAUDE.md once via `anti-slop-interview` — every other skill (this one included) gets sharper.

## Push to Mission Control (optional)

If you have Mission Control running on `localhost:8080`, the skill will offer to push each outlier into your Ideation section as a content idea — with the title variants already attached as notes. From there it's one click to move into scripting.

## Cost

Zero. YouTube API free tier covers ~16 runs / day. No paid services required (Apify optional).

## Pairs well with

- [`anti-slop-interview`](https://github.com/criscatalyst/anti-slop-interview-skill) — bootstrap your CLAUDE.md so outliers gets your niche right.
- [`script-writer-skill`](https://github.com/criscatalyst/script-writer-skill) — once you pick a title variant, generate the full script with Hook → Build-Up → Value → Payoff → CTA.
- [`hemingway-skill`](https://github.com/criscatalyst/hemingway-skill) — readability check on the script before you record.

## Stack

- `google-api-python-client` — YouTube Data API v3
- `python-dotenv` — env var loading
- `youtube-transcript-api` — transcript fetching (when enabled)

— Cris
