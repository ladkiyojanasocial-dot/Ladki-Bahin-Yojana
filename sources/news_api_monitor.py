"""
NewsAPI Monitor - Fetches top headlines and rotating scheme queries.
"""
import logging
import hashlib
from datetime import datetime, timedelta

from newsapi import NewsApiClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from detection.scheme_registry import get_trends_keywords

logger = logging.getLogger(__name__)


def _hash_story(title, url):
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_rotating_queries():
    base_queries = [
        "agriculture india",
        "farmer scheme india",
        "agriculture minister india",
        "MSP minimum support price",
        "kharif rabi crop india",
        "mandi prices india",
    ]
    scheme_queries = get_trends_keywords(limit=60)
    all_q = base_queries + scheme_queries
    seen = set()
    dedup = []
    for q in all_q:
        k = q.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        dedup.append(q.strip())

    max_q = getattr(config, "NEWSAPI_ROTATING_QUERY_COUNT", 10)
    hour = datetime.utcnow().hour
    start = (hour * 2) % max(len(dedup), 1)
    ring = dedup[start:] + dedup[:start]
    return ring[:max_q]


def fetch_news_headlines():
    stories = []
    rate_limited = False

    try:
        newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize NewsAPI client: {e}")
        return stories

    try:
        logger.info("NewsAPI: Fetching top headlines for agriculture in India")
        top = newsapi.get_top_headlines(q="agriculture OR farmer", country="in", page_size=20)
        if top.get("status") == "ok":
            for article in top.get("articles", []):
                title = article.get("title", "")
                if not title or title == "[Removed]":
                    continue
                stories.append({
                    "title": title.strip(),
                    "summary": (article.get("description") or "").strip()[:500],
                    "url": article.get("url", ""),
                    "source": f"NewsAPI/{article.get('source', {}).get('name', 'Unknown')}",
                    "source_type": "newsapi",
                    "matched_keyword": "agriculture",
                    "published_at": _parse_date(article.get("publishedAt")),
                    "story_hash": _hash_story(title, article.get("url", "")),
                    "image_url": article.get("urlToImage", ""),
                })
    except Exception as e:
        logger.error(f"NewsAPI top headlines error: {e}")
        if "rateLimited" in str(e):
            rate_limited = True

    search_queries = _build_rotating_queries()
    if rate_limited:
        logger.warning("NewsAPI rate limit reached; skipping query loop for this cycle")
        search_queries = []
    for query in search_queries:
        try:
            from_date = (datetime.utcnow() - timedelta(hours=30)).strftime("%Y-%m-%d")
            results = newsapi.get_everything(
                q=query,
                language="en",
                sort_by="publishedAt",
                from_param=from_date,
                page_size=8,
            )
            if results.get("status") == "ok":
                for article in results.get("articles", []):
                    title = article.get("title", "")
                    if not title or title == "[Removed]":
                        continue
                    stories.append({
                        "title": title.strip(),
                        "summary": (article.get("description") or "").strip()[:500],
                        "url": article.get("url", ""),
                        "source": f"NewsAPI/{article.get('source', {}).get('name', 'Unknown')}",
                        "source_type": "newsapi",
                        "matched_keyword": query.lower(),
                        "published_at": _parse_date(article.get("publishedAt")),
                        "story_hash": _hash_story(title, article.get("url", "")),
                        "image_url": article.get("urlToImage", ""),
                    })
        except Exception as e:
            logger.error(f"NewsAPI everything error for '{query}': {e}")
            if "rateLimited" in str(e):
                rate_limited = True
                break
            continue

    seen_hashes = set()
    unique_stories = []
    for story in stories:
        if story["story_hash"] not in seen_hashes:
            seen_hashes.add(story["story_hash"])
            unique_stories.append(story)

    exclude_kws = getattr(config, "EXCLUDE_KEYWORDS", [])
    filtered = []
    excluded = 0
    for story in unique_stories:
        text = f"{story.get('title', '')} {story.get('summary', '')}".lower()
        if any(kw.lower() in text for kw in exclude_kws):
            excluded += 1
            continue
        filtered.append(story)

    if excluded > 0:
        logger.info(f"NewsAPI Monitor: Excluded {excluded} irrelevant stories")

    logger.info(f"NewsAPI Monitor: Found {len(filtered)} relevant stories (from {len(stories)} total)")
    return filtered


def _parse_date(date_str):
    if not date_str:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()

