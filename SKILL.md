---
name: outliers
description: YouTube cross-niche outlier detection. Finds videos that massively over-performed their channel's average (5x, 10x, 20x normal views), then generates 3 personalized title variants for each — adapted to the user's niche from their ~/CLAUDE.md. Trigger when the user says "find outliers", "outlier hunt", "/outliers", "show me viral videos in <topic>", or asks for content ideas based on what's working in adjacent niches.
---

# Outliers

Cross-niche YouTube outlier detection + title variant generation. Finds videos that radically outperformed their channel baseline (computed as views ÷ channel median), filters out the user's own niche, and proposes 3 title variants adapted to the user's brand.

The "cross-niche" part is the value: if you only watch your own niche, you only see the same patterns. Outliers from adjacent niches surface hooks you wouldn't have thought of — but you can adapt them.

## When to trigger

- User says "find outliers", "outlier hunt", "/outliers"
- User pastes a topic and asks for viral examples ("what's working in fitness right now")
- User asks for content ideas based on what's performing on YouTube
- Weekly content planning sessions

## How to invoke

The script lives next to this SKILL.md. Run it from the skill folder:

```bash
cd ~/.claude/skills/outliers
source venv/bin/activate 2>/dev/null || (python3 -m venv venv && source venv/bin/activate && pip install -q -r requirements.txt)

ARGS="$1"
if [ -z "$ARGS" ]; then
  python outlier_detector.py --skip_transcripts
elif [[ "$ARGS" == --* ]]; then
  python outlier_detector.py $ARGS
else
  python outlier_detector.py --terms "$ARGS" --skip_transcripts
fi
```

Common usage:
- No args → full run, default keywords (creator economy, personal brand, content creation, digital products, solopreneur, side hustle), skip transcripts
- Bare topic → auto-wrapped into `--terms "<topic>"`
- `--queries 1` → single keyword test (cheapest on YouTube quota)
- `--queries 2 --min_score 3` → 2 keywords, higher outlier threshold
- `--terms "business growth" "money"` → explicit custom keywords (multi)
- `--limit 5` → top 5 only

## Steps

### 1. Run the detector

Use the bash block above. The script writes a JSON file to `~/.claude/skills/outliers/output/`.

### 2. Read the latest output JSON

Find the newest file in `output/` and load it. Each entry contains: title, channel, views, days_old, score (outlier multiplier), URL, optional transcript_excerpt.

### 3. Generate 3 title variants per outlier

Read `~/CLAUDE.md` (Voice rules, Anti-slop rules, Offer & goals sections) to learn the user's niche, ICP, and voice.

For **each outlier**, generate 3 title variants that:
- Adapt the hook structure / emotional trigger / curiosity gap to the user's niche (pulled from CLAUDE.md "Offer & goals" + "About me")
- Keep the same psychological mechanism that made the original work (pattern interrupt, contrarian claim, specific number, etc.)
- Are meaningfully different from each other (vary angle, specificity, framing)
- Stay under 100 characters
- Match the user's voice rules from CLAUDE.md (no AI tells, no banned words)
- Are written in the user's content language (auto-detect from CLAUDE.md or ask)

If `~/CLAUDE.md` doesn't exist or has no Offer & goals section, ask the user once for: niche + ICP one-liner. Don't proceed with generic variants.

### 4. Generate brief summary (when transcript is available)

If `transcript_excerpt` is present, write 2–3 sentences:
- The hook / angle the video uses
- Why it works psychologically
- How to adapt it to the user's niche

If no transcript, skip this step for that outlier.

### 5. Present the results

For each outlier:

```
**#N — "Original Title" (SCORE x outlier)**
Channel | Views | Days old | Category
URL

Hook analysis: [1-2 sentences on why this hook works]

Title variants:
1. "Variant 1"
2. "Variant 2"
3. "Variant 3"
```

### 6. Optional: push to Mission Control

After presenting, ask: *"Push these to Mission Control as ideas?"*

If yes (and Mission Control is running on `localhost:8080`):

```bash
/usr/bin/curl -s -X POST http://localhost:8080/api/ideas/new \
  -H "Content-Type: application/json" \
  -d '{"hook": "ORIGINAL_TITLE", "angle": "CHANNEL | VIEWS views | SCOREx outlier", "type": "viral", "notes": "Title variants:\n1. V1\n2. V2\n3. V3\nURL: VIDEO_URL"}'
```

If Mission Control isn't running, say so and offer to skip.

## Setup requirements

- **YouTube Data API v3 key** — free at https://console.cloud.google.com (enable YouTube Data API v3 → create API key). Free tier: 10,000 quota units/day. Each run uses ~800 units.
- **Apify API token** *(optional)* — for transcript fetching. Free at https://apify.com.
- A `.env` file in the skill folder with `YOUTUBE_API_KEY=...` and optionally `APIFY_API_TOKEN=...`.

If `.env` is missing, tell the user to copy `.env.example` to `.env` and fill it.

## Cost / quota notes

- Default run with all 6 keywords: ~600 quota units. You can do ~16 runs per day on the free tier.
- `--queries 1` uses ~100 units. Good for testing.
- If quota hits the daily cap, the script returns an empty result with an error. Tell the user to wait until midnight Pacific Time (when YouTube resets) or use `--queries 1`.

## Anti-patterns

- ❌ Don't generate generic title variants. They must reference the user's specific niche/ICP.
- ❌ Don't push to Mission Control without asking first.
- ❌ Don't run the script without checking that `.env` is set up — it'll fail silently with a confusing error.
- ❌ Don't suggest topics that aren't actual YouTube outliers — the value is the data.

## Why this skill exists

Most creators draw content ideas from their own niche bubble — same hooks, same patterns, same diminishing returns. Cross-niche outliers surface what's working *next door*, where competition is lower. Adapting a finance hook to fitness, or a fitness hook to creator economy, is how new niches get built.
