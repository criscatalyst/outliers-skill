#!/usr/bin/env python3
"""
Cross-Niche Outlier Detection using YouTube Data API v3.
Adapted for @criscatalyst — personal branding, creator economy, AI for creators.

Calculates outlier scores by comparing video views against the channel's
median views (last N videos). Free tier: 10,000 quota units/day.

Key features:
- Uses YouTube Data API v3 (free, ~800 units per run)
- Outlier score = video views / channel median views
- Cross-niche filtering and title variant generation via Claude
- Local JSON output (no Google Sheets dependency)
- Optional push to Mission Control dashboard as ideas

Usage:
    # Default: search all default terms
    python outlier_detector.py

    # Single query test (cheapest)
    python outlier_detector.py --queries 1

    # Custom search terms
    python outlier_detector.py --terms "business growth" "entrepreneur" "productivity"

    # Push top outliers to Mission Control dashboard
    python outlier_detector.py --push-dashboard --limit 10

    # Skip transcripts (faster)
    python outlier_detector.py --skip_transcripts
"""

import os
import sys
import json
import time
import datetime
import argparse
import html
import re
import statistics
import unicodedata
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from googleapiclient.discovery import build

# Load .env from the script's own directory
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# YouTube Data API v3
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Default search terms (broad to maximize cross-niche results)
DEFAULT_SEARCH_TERMS = [
    "creator economy",
    "personal brand",
    "content creation",
    "digital products",
    "solopreneur",
    "side hustle",
]

# =============================================================================
# EXCLUSION FILTERS
# =============================================================================

# OWN NICHE - Hard exclude (we want CROSS-niche, not our niche)
OWN_NICHE_TERMS = [
    # Cris's own niche — too close, not cross-niche
    "personal brand", "instagram growth", "skool", "whop", "content creation tips",
    # AI/ML Core
    "ai", "a.i.", "a.i", " ai ", "artificial intelligence",
    "gpt", "chatgpt", "chat gpt", "claude", "llm", "gemini",
    "machine learning", "neural network", "deep learning", "openai", "anthropic",
    "midjourney", "stable diffusion", "dall-e", "copilot",
    # Automation Tools
    "automation", "automate", "automated", "n8n", "make.com", "zapier", "workflow",
    "integromat", "power automate", "ifttt", "airtable automation",
    # Agents/Frameworks
    "agent", "agentic", "langchain", "langgraph", "crewai", "autogen", "autogpt",
    "babyagi", "superagi", "agent gpt", "ai agent",
    # Code/Dev
    "code", "coding", "programming", "programmer", "developer", "python", "javascript",
    "typescript", "api", "sdk", "github", "open source", "repository", "deploy",
    "docker", "kubernetes", "aws", "serverless", "backend", "frontend", "full stack",
    # Tech Tools
    "cursor", "replit", "vs code", "vscode", "terminal", "command line", "cli",
    "notion ai", "obsidian", "roam research",
]

# NON-TRANSFERABLE FORMATS - Heavy penalty
EXCLUDE_FORMATS = [
    # Gear/Tech Reviews
    "setup", "desk setup", "tour", "room tour", "office tour", "studio tour",
    "carry", "every day carry", "edc", "what's in my bag",
    "buying guide", "review", "unboxing", "hands on", "first look",
    "best laptop", "best phone", "best camera", "best mic", "best keyboard",
    "vs", "comparison", "compared", "which is better", "versus",
    "upgrade", "upgraded my", "new setup",
    # Entertainment/Challenges
    "challenge", "challenged", "survive", "survived", "surviving",
    "win $", "won $", "winning", "prize", "giveaway",
    "battle", "competition", "race", "contest",
    "prank", "pranked", "pranking",
    "react", "reacts", "reacting", "reaction",
    "roast", "roasted", "roasting",
    "exposed", "exposing", "drama", "beef", "cancelled",
    # Personal/Lifestyle
    "day in my life", "day in the life", "a day with",
    "morning routine", "night routine", "evening routine", "my routine",
    "what i eat", "what i ate", "full day of eating", "diet",
    "get ready with me", "grwm", "outfit", "fashion haul", "try on",
    "room makeover", "apartment tour", "house tour", "home tour",
    "travel vlog", "vacation", "trip to", "visiting",
    "wedding", "birthday", "anniversary", "holiday",
    "workout", "gym routine", "fitness routine", "exercise",
    # Low-Value Content
    "q&a", "ama", "ask me anything", "answering your questions",
    "reading comments", "responding to", "replying to",
    "shorts", "short", "#shorts", "tiktok", "reel",
    "clip", "clips", "highlight", "highlights", "compilation", "best of",
    "podcast ep", "full episode", "full interview",
    "live stream", "livestream", "streaming",
    "behind the scenes", "bts", "how we made",
    "bloopers", "outtakes", "deleted scenes",
    # News/Current Events
    "breaking", "just announced", "breaking news",
    "news", "update", "updates", "announcement",
    "what happened", "drama explained",
    "election", "vote", "political", "trump", "biden", "congress",
    "israel", "palestine", "ukraine", "russia", "iran", "china",
    "inflation", "recession", "fed", "federal reserve",
    "crypto", "bitcoin", "ethereum", "cryptocurrency",
    "stock market", "stocks", "economy news",
    "immigration", "border", "deport",
    # Music/Gaming/ASMR
    "music video", "official video", "official audio", "lyric video",
    "gameplay", "playthrough", "walkthrough", "let's play",
    "minecraft", "fortnite", "valorant", "gaming",
    "asmr", "mukbang", "relaxing", "sleep",
]

# Positive scoring hooks
MONEY_HOOKS = [
    "$", "revenue", "income", "profit", "money", "earn", "cash", "wealthy",
    "million", "millionaire", "billionaire", "rich", "wealth", "net worth",
    "salary", "raise", "pricing", "charge more", "high ticket", "premium"
]

TIME_HOOKS = [
    "faster", "save time", "productivity", "efficient", "quick", "speed",
    "in minutes", "in seconds", "instantly", "overnight", "shortcut",
    "hack", "hacks", "cheat code", "fast track", "accelerate"
]

CURIOSITY_HOOKS = [
    "?", "secret", "secrets", "nobody", "no one tells you", "they don't want",
    "this changed", "changed everything", "game changer", "mind blown",
    "shocking", "surprised", "unexpected", "plot twist",
    "never", "always", "stop", "don't", "quit", "avoid",
    "truth about", "real reason", "actually", "really",
    "hidden", "underground", "insider", "exclusive"
]

TRANSFORMATION_HOOKS = [
    "before", "after", "transformed", "transformation",
    "from zero", "from nothing", "started with",
    "how i went", "how i built", "journey",
    "changed my life", "life changing", "breakthrough"
]

CONTRARIAN_HOOKS = [
    "wrong", "mistake", "mistakes", "myth", "myths", "lie", "lies",
    "overrated", "underrated", "unpopular opinion", "controversial",
    "why i stopped", "why i quit", "the problem with",
    "nobody talks about", "uncomfortable truth"
]

URGENCY_HOOKS = [
    "before it's too late", "while you still can", "last chance",
    "now or never", "running out", "limited", "ending soon",
    "don't miss", "must watch", "need to know"
]

# Non-Latin scripts to drop from results (English-only filter, layer 1)
NON_LATIN_SCRIPTS = (
    "MALAYALAM", "TELUGU", "TAMIL", "DEVANAGARI", "BENGALI", "GUJARATI",
    "GURMUKHI", "KANNADA", "ORIYA", "SINHALA",
    "ARABIC", "HEBREW",
    "CJK", "HIRAGANA", "KATAKANA", "HANGUL",
    "CYRILLIC", "GREEK", "THAI", "LAO", "MYANMAR", "KHMER",
)


def has_non_latin_script(text):
    """True if text contains alphabetic chars from non-Latin scripts."""
    for char in text:
        if not char.isalpha():
            continue
        try:
            name = unicodedata.name(char, "")
        except ValueError:
            continue
        if any(script in name for script in NON_LATIN_SCRIPTS):
            return True
    return False


# User's channel context
USER_CHANNEL_NICHE = "personal branding, creator economy, content creation systems, AI for creators, digital products"

# Target audience for title variant generation
TARGET_AUDIENCE = (
    "pre-revenue creators aged 19-28 who want to monetize their personal brand, "
    "build content systems with AI, and sell digital products"
)


def get_channel_median_views(youtube, channel_id, max_videos=30, cache=None):
    """
    Calculate the median view count for a channel's recent videos.

    Uses the uploads playlist (UC→UU trick) to get recent video IDs,
    then fetches their stats.

    Args:
        youtube: YouTube API client
        channel_id: Channel ID (UC...)
        max_videos: How many recent videos to sample (default 30)
        cache: Optional dict to cache results per channel

    Returns:
        Median view count (float), or 1.0 if unavailable
    """
    if cache is not None and channel_id in cache:
        return cache[channel_id]

    try:
        # UC... → UU... gives us the uploads playlist
        uploads_playlist_id = "UU" + channel_id[2:]

        # Get recent video IDs from uploads playlist
        pl_response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part="contentDetails",
            maxResults=max_videos
        ).execute()

        video_ids = [
            item["contentDetails"]["videoId"]
            for item in pl_response.get("items", [])
        ]

        if not video_ids:
            if cache is not None:
                cache[channel_id] = 1.0
            return 1.0

        # Fetch stats for those videos (batch of up to 50)
        stats_response = youtube.videos().list(
            id=",".join(video_ids),
            part="statistics"
        ).execute()

        view_counts = []
        for item in stats_response.get("items", []):
            vc = int(item["statistics"].get("viewCount", 0))
            if vc > 0:
                view_counts.append(vc)

        if not view_counts:
            median = 1.0
        else:
            median = statistics.median(view_counts)

        if cache is not None:
            cache[channel_id] = median

        return median

    except Exception as e:
        print(f"    Warning: could not get median for channel {channel_id}: {str(e)[:80]}")
        if cache is not None:
            cache[channel_id] = 1.0
        return 1.0


def search_youtube_outliers(youtube, query, max_results=50, min_views=10000,
                            published_after=None, channel_videos=30, channel_cache=None):
    """
    Search YouTube for outlier videos using YouTube Data API v3.

    Steps:
    1. Search for videos matching the query
    2. Fetch video stats (views, likes, comments)
    3. For each unique channel, calculate median views
    4. outlier_score = video views / channel median

    Args:
        youtube: YouTube API client
        query: Search term
        max_results: Max results per query (API max 50)
        min_views: Minimum view count filter
        published_after: ISO 8601 date string
        channel_videos: How many channel videos to sample for median
        channel_cache: Shared dict for caching channel medians

    Returns:
        List of video dicts
    """
    try:
        # Step 1: Search for videos
        search_params = {
            "q": query,
            "type": "video",
            "part": "snippet",
            "maxResults": min(max_results, 50),
            "order": "viewCount",
            "relevanceLanguage": "en",
            "regionCode": "US",  # bias SERP toward US-popular content (English bias)
            "videoDuration": "medium",  # 4-20 min (excludes shorts)
        }
        if published_after:
            search_params["publishedAfter"] = published_after

        search_response = youtube.search().list(**search_params).execute()

        items = search_response.get("items", [])
        if not items:
            return []

        # Collect video IDs and snippet data
        video_ids = []
        snippet_map = {}
        for item in items:
            vid = item["id"]["videoId"]
            video_ids.append(vid)
            snippet_map[vid] = item["snippet"]

        # Step 2: Fetch video statistics in one batch
        # Include snippet to access defaultAudioLanguage for English-only filtering
        stats_response = youtube.videos().list(
            id=",".join(video_ids),
            part="statistics,contentDetails,snippet"
        ).execute()

        video_stats = {}
        for item in stats_response.get("items", []):
            video_stats[item["id"]] = item

        # Step 3: Calculate channel medians for unique channels
        unique_channels = set()
        for vid in video_ids:
            snippet = snippet_map.get(vid, {})
            ch_id = snippet.get("channelId", "")
            if ch_id:
                unique_channels.add(ch_id)

        print(f"    Fetching medians for {len(unique_channels)} unique channels...")
        for ch_id in unique_channels:
            get_channel_median_views(youtube, ch_id, max_videos=channel_videos, cache=channel_cache)

        # Step 4: Build video list with outlier scores
        videos = []
        skipped_non_latin = 0
        skipped_non_english_audio = 0
        skipped_gaming = 0
        for vid in video_ids:
            snippet = snippet_map.get(vid, {})
            stats_item = video_stats.get(vid)
            if not stats_item:
                continue

            # Decode HTML entities (YouTube returns &#39;, &amp;, &quot; etc.)
            title = html.unescape(snippet.get("title", ""))

            # English-only filter, layer 1: drop titles containing non-Latin scripts
            if has_non_latin_script(title):
                skipped_non_latin += 1
                continue

            # English-only filter, layer 2: defaultAudioLanguage from videos.list snippet.
            # Catches Latin-script titles with non-English audio (e.g. "... | Telugu Guide").
            video_snippet = stats_item.get("snippet", {})
            audio_lang = (video_snippet.get("defaultAudioLanguage")
                          or video_snippet.get("defaultLanguage")
                          or "")
            if audio_lang and not audio_lang.lower().startswith("en"):
                skipped_non_english_audio += 1
                continue

            # Hard-exclude YouTube category 20 = Gaming.
            # Catches GTA / Genshin / Roblox / etc. that sneak through keyword filters.
            if video_snippet.get("categoryId") == "20":
                skipped_gaming += 1
                continue

            stats = stats_item.get("statistics", {})
            view_count = int(stats.get("viewCount", 0))

            # Apply min_views filter
            if view_count < min_views:
                continue

            channel_id = snippet.get("channelId", "")
            channel_median = channel_cache.get(channel_id, 1.0) if channel_cache else 1.0

            # Parse duration (ISO 8601 duration → seconds)
            duration_str = stats_item.get("contentDetails", {}).get("duration", "PT0S")
            duration_seconds = _parse_iso_duration(duration_str)

            # Skip shorts (< 61s)
            if duration_seconds < 61:
                continue

            # Thumbnail
            thumbnails = snippet.get("thumbnails", {})
            thumb_url = (
                thumbnails.get("high", {}).get("url") or
                thumbnails.get("medium", {}).get("url") or
                thumbnails.get("default", {}).get("url") or
                f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
            )

            # Parse publish date
            published_at = snippet.get("publishedAt", "")
            date_str = ""
            days_old = 999
            if published_at:
                try:
                    pub_date = datetime.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    date_str = pub_date.strftime("%Y%m%d")
                    days_old = (datetime.datetime.now(datetime.timezone.utc) - pub_date).days
                except Exception:
                    pass

            outlier_score = round(view_count / channel_median, 2) if channel_median > 0 else 0

            video = {
                "video_id": vid,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "view_count": view_count,
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
                "duration": duration_seconds,
                "channel_name": snippet.get("channelTitle", ""),
                "channel_id": channel_id,
                "channel_median_views": int(channel_median),
                "thumbnail_url": thumb_url,
                "date": date_str,
                "days_old": days_old,
                "outlier_score": outlier_score,
                "source": f"youtube: {query}",
            }
            videos.append(video)

        if skipped_non_latin or skipped_non_english_audio or skipped_gaming:
            print(f"    Filters: dropped {skipped_non_latin} non-Latin titles, "
                  f"{skipped_non_english_audio} non-English audio, "
                  f"{skipped_gaming} gaming category")

        return videos

    except Exception as e:
        print(f"  YouTube API error: {str(e)[:150]}")
        return []


def _parse_iso_duration(duration_str):
    """Parse ISO 8601 duration (PT#H#M#S) to seconds."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def calculate_cross_niche_score(title, base_outlier_score):
    """
    Calculate cross-niche potential score with comprehensive filtering.
    Returns 0 for hard-excluded content.
    """
    title_lower = title.lower()
    score = base_outlier_score

    # Hard exclude own niche
    if any(term in title_lower for term in OWN_NICHE_TERMS):
        return 0

    # Heavy penalty for non-transferable formats
    if any(fmt in title_lower for fmt in EXCLUDE_FORMATS):
        score *= 0.3

    # Bonuses for proven hooks
    if any(hook in title_lower for hook in MONEY_HOOKS):
        score *= 1.4
    if any(hook in title_lower for hook in CURIOSITY_HOOKS):
        score *= 1.3
    if any(hook in title_lower for hook in TRANSFORMATION_HOOKS):
        score *= 1.25
    if any(hook in title_lower for hook in CONTRARIAN_HOOKS):
        score *= 1.25
    if any(hook in title_lower for hook in TIME_HOOKS):
        score *= 1.2
    if any(hook in title_lower for hook in URGENCY_HOOKS):
        score *= 1.15
    if re.search(r'\b\d+\b', title):
        score *= 1.1

    return round(score, 2)


def categorize_content(title):
    """Auto-categorize content type."""
    title_lower = title.lower()

    if any(word in title_lower for word in ["money", "revenue", "income", "profit", "$", "million"]):
        return "Money"
    elif any(word in title_lower for word in ["productivity", "time", "efficient", "faster"]):
        return "Productivity"
    elif any(word in title_lower for word in ["youtube", "content", "creator", "channel"]):
        return "Creator"
    elif any(word in title_lower for word in ["business", "startup", "founder", "entrepreneur"]):
        return "Business"
    else:
        return "General"


def fetch_transcript(video_id):
    """Fetch transcript using youtube-transcript-api with Apify fallback."""
    if not video_id:
        return None

    # Try youtube-transcript-api first
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        time.sleep(1)  # Rate limit
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = ' '.join([entry['text'] for entry in transcript])
        return text
    except Exception as e:
        print(f"    [transcript] youtube_transcript_api failed: {e}")

    # Fallback to Apify
    apify_token = os.getenv("APIFY_API_TOKEN")
    if not apify_token:
        return None

    try:
        from apify_client import ApifyClient
        client = ApifyClient(apify_token)
        run = client.actor("karamelo/youtube-transcripts").call(
            run_input={"urls": [f"https://www.youtube.com/watch?v={video_id}"]},
            timeout_secs=120
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if items and "captions" in items[0]:
            return " ".join(items[0]["captions"])
    except Exception as e:
        print(f"    [transcript] Apify fallback failed: {e}")

    return None


def process_outlier_content(outlier, index, total, skip_transcripts=False):
    """Process a single outlier: fetch transcript and categorize."""
    title_short = outlier['title'][:50] + "..." if len(outlier['title']) > 50 else outlier['title']
    print(f"\n  [{index}/{total}] {title_short}")

    if skip_transcripts:
        outlier["transcript_excerpt"] = ""
    else:
        print(f"    Fetching transcript...")
        transcript = fetch_transcript(outlier["video_id"])

        if transcript:
            print(f"    Got transcript ({len(transcript)} chars)")
            outlier["transcript_excerpt"] = transcript[:8000]
        else:
            print(f"    No transcript available")
            outlier["transcript_excerpt"] = ""

    outlier["category"] = categorize_content(outlier["title"])
    print(f"    Done")
    return outlier


def push_to_dashboard(outliers, limit):
    """Push top outliers to Mission Control dashboard as ideas."""
    pushed = 0
    failed = 0

    for outlier in outliers[:limit]:
        # Build the idea payload
        payload = {
            "hook": outlier["title"],
            "angle": f"{outlier['channel_name']} | {outlier['view_count']:,} views | {outlier.get('cross_niche_score', outlier['outlier_score'])}x outlier",
            "type": "viral",
            "notes": f"URL: {outlier['url']}"
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:8080/api/ideas/new",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            pushed += 1
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            if failed == 0:
                print(f"  WARNING: Dashboard push failed ({str(e)[:80]}). Continuing...")
            failed += 1

    print(f"\n  Dashboard: {pushed} ideas pushed, {failed} failed")
    return pushed


def save_results_json(outliers, output_path):
    """Save results to a JSON file."""
    # Prepare output (exclude raw transcript from JSON to keep file size reasonable)
    output_data = {
        "generated_at": datetime.datetime.now().isoformat(),
        "total_outliers": len(outliers),
        "outliers": []
    }

    for o in outliers:
        entry = {
            "cross_niche_score": o.get("cross_niche_score", 0),
            "outlier_score": o["outlier_score"],
            "title": o["title"],
            "url": o["url"],
            "thumbnail_url": o["thumbnail_url"],
            "view_count": o["view_count"],
            "like_count": o.get("like_count", 0),
            "comment_count": o.get("comment_count", 0),
            "duration_minutes": round(o.get("duration", 0) / 60, 1),
            "days_old": o.get("days_old", None),
            "channel_name": o["channel_name"],
            "channel_median_views": o.get("channel_median_views", 0),
            "category": o.get("category", "Unknown"),
            "transcript_excerpt": o.get("transcript_excerpt", ""),
            "date": o.get("date", ""),
            "source": o.get("source", ""),
        }
        output_data["outliers"].append(entry)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return output_path


def print_summary(outliers):
    """Print a readable summary of top outliers to stdout."""
    print("\n" + "=" * 70)
    print("  TOP CROSS-NICHE OUTLIERS")
    print("=" * 70)

    for i, o in enumerate(outliers, 1):
        score = o.get("cross_niche_score", o["outlier_score"])
        views = o["view_count"]
        channel = o["channel_name"]
        title = o["title"]
        category = o.get("category", "?")

        print(f"\n  #{i}  [{score}x] {title}")
        print(f"       {channel} | {views:,} views | {o.get('days_old', '?')}d old | {category}")
        print(f"       {o['url']}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Cross-niche outlier detection via YouTube Data API v3 for @criscatalyst"
    )
    parser.add_argument("--terms", nargs="+", help="Custom search terms (overrides defaults)")
    parser.add_argument("--queries", type=int, default=None,
                        help="Number of queries — picks first N default terms (default: all)")
    parser.add_argument("--results", type=int, default=50,
                        help="Results per query (max 50, API limit)")
    parser.add_argument("--min_views", type=int, default=10000, help="Minimum view count")
    parser.add_argument("--max_days", type=int, default=30, help="Max age in days (default: 30)")
    parser.add_argument("--min_score", type=float, default=1.5,
                        help="Minimum cross-niche score after filtering")
    parser.add_argument("--limit", type=int, default=10, help="Max outliers to process/push (default: 10)")
    parser.add_argument("--channel-videos", type=int, default=30,
                        help="Videos to sample for channel median (default: 30)")
    parser.add_argument("--skip_transcripts", action="store_true", help="Skip transcript fetching")
    parser.add_argument("--push-dashboard", action="store_true",
                        help="Push top results as ideas to Mission Control")
    parser.add_argument("--output", type=str, default=None,
                        help="Custom output path (default: output/outliers_<timestamp>.json)")
    parser.add_argument("--workers", type=int, default=3,
                        help="Parallel workers for content processing")

    args = parser.parse_args()

    if not YOUTUBE_API_KEY:
        print("ERROR: YOUTUBE_API_KEY not set in .env")
        print(f"       Edit: {os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')}")
        print()
        print("  To get a free API key:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Enable 'YouTube Data API v3'")
        print("  3. Create an API key (Credentials → Create Credentials → API Key)")
        return 1

    # Build YouTube API client
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    # Determine search terms
    if args.terms:
        search_terms = args.terms
    elif args.queries is not None:
        search_terms = DEFAULT_SEARCH_TERMS[:args.queries]
    else:
        search_terms = DEFAULT_SEARCH_TERMS

    # Estimate quota usage
    estimated_quota = len(search_terms) * 100  # search.list = 100 units each
    estimated_quota += len(search_terms)  # videos.list stats batches
    # Channel medians: rough estimate ~200 units for playlist + stats calls
    estimated_quota += 200

    print(f"Cross-Niche Outlier Detection (YouTube Data API v3)")
    print(f"  Niche: {USER_CHANNEL_NICHE}")
    print(f"  Search terms: {search_terms}")
    print(f"  Results per query: {args.results}")
    print(f"  Min views: {args.min_views:,}")
    print(f"  Max age: {args.max_days} days")
    print(f"  Min cross-niche score: {args.min_score}")
    print(f"  Limit: {args.limit}")
    print(f"  Channel sample size: {args.channel_videos} videos")
    print(f"  Estimated quota: ~{estimated_quota}/10,000 units")
    print()

    # Calculate published_after date for server-side filtering
    published_after = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=args.max_days)
    ).strftime("%Y-%m-%dT00:00:00Z")
    print(f"  Date filter: {published_after}")
    print()

    # Shared cache for channel median views (avoids re-fetching same channel)
    channel_cache = {}

    # Step 1: Fetch outliers from YouTube
    print("Searching YouTube for outlier candidates...")
    all_videos = []

    for term in search_terms:
        print(f"  Searching: {term}")
        videos = search_youtube_outliers(
            youtube=youtube,
            query=term,
            max_results=args.results,
            min_views=args.min_views,
            published_after=published_after,
            channel_videos=args.channel_videos,
            channel_cache=channel_cache,
        )
        print(f"    Found {len(videos)} videos (filtered by views/duration)")
        all_videos.extend(videos)

    # Deduplicate
    seen = set()
    unique_videos = []
    for v in all_videos:
        if v["video_id"] not in seen:
            seen.add(v["video_id"])
            unique_videos.append(v)

    print(f"\nFound {len(unique_videos)} unique videos")

    # Step 2: Apply cross-niche scoring and filtering
    print("\nApplying cross-niche filters...")
    outliers = []
    filtered_own_niche = 0
    filtered_low_score = 0

    for video in unique_videos:
        cross_score = calculate_cross_niche_score(video["title"], video["outlier_score"])

        if cross_score == 0:
            filtered_own_niche += 1
            continue

        if cross_score < args.min_score:
            filtered_low_score += 1
            continue

        video["cross_niche_score"] = cross_score
        outliers.append(video)

    print(f"  Filtered {filtered_own_niche} own-niche videos")
    print(f"  Filtered {filtered_low_score} low cross-niche score videos")
    print(f"  Remaining: {len(outliers)} outliers")

    # Sort by cross-niche score (highest first), then by date
    outliers.sort(key=lambda x: (x.get("cross_niche_score", 0), x.get("date", "")), reverse=True)

    # Apply limit
    outliers = outliers[:args.limit]

    if not outliers:
        print("\nNo outliers found with current criteria. Try lowering --min_score.")
        return 0

    # Step 3: Process content (transcripts, summaries, variants)
    print(f"\nProcessing {len(outliers)} outliers...")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                process_outlier_content,
                outlier, i, len(outliers),
                args.skip_transcripts
            ): outlier
            for i, outlier in enumerate(outliers, 1)
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"    Error: {str(e)}")

    # Step 4: Save to JSON
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(script_dir, "output", f"outliers_{timestamp}.json")

    saved_path = save_results_json(outliers, output_path)
    print(f"\nResults saved to: {saved_path}")

    # Step 5: Optional dashboard push
    if args.push_dashboard:
        print(f"\nPushing top {args.limit} outliers to Mission Control...")
        push_to_dashboard(outliers, args.limit)

    # Step 6: Print summary
    print_summary(outliers)

    print(f"\nDone! Processed {len(outliers)} cross-niche outliers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
