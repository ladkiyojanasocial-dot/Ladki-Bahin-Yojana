"""
RSS Feed Monitor - Fetches and filters women-welfare stories from major Indian news feeds.
"""
import feedparser
import hashlib
import logging
import re
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def _normalize(text):
    """Lowercase and strip special chars for keyword matching."""
    return re.sub(r'[^a-z0-9\s]', '', text.lower())


def _matches_keywords(text, keywords=None):
    """Check if text matches any configured women-welfare keywords."""
    if keywords is None:
        keywords = config.ALL_KEYWORDS
    normalized = _normalize(text)
    for kw in keywords:
        if kw.lower() in normalized:
            return True, kw
    return False, None


def _hash_story(title, url):
    """Create a unique hash for a story based on title + URL."""
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def fetch_rss_stories():
    """
    Fetch stories from all configured RSS feeds and filter for women-welfare relevance.
    """
    stories = []

    for feed_name, feed_url in config.RSS_FEEDS.items():
        try:
            logger.info(f"Fetching RSS: {feed_name}")
            feed = feedparser.parse(
                feed_url,
                agent="LadkiBahinAgent/1.0 (RSS; +https://womenempowermentportal.org)",
                request_headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"},
            )

            if feed.bozo and not feed.entries:
                logger.warning(f"RSS feed error for {feed_name}: {feed.bozo_exception}")
                continue

            is_agri_only_feed = getattr(config, "AGRI_ONLY_FEEDS", []) and feed_name in getattr(config, "AGRI_ONLY_FEEDS", [])

            for entry in feed.entries[:30]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")

                combined_text = f"{title} {summary}"
                if is_agri_only_feed:
                    is_match, matched_keyword = True, "women welfare"
                else:
                    is_match, matched_keyword = _matches_keywords(combined_text)

                if is_match:
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            published = datetime(*entry.published_parsed[:6])
                        except Exception:
                            published = datetime.utcnow()
                    else:
                        published = datetime.utcnow()

                    story = {
                        "title": title.strip(),
                        "summary": summary.strip()[:500],
                        "url": link.strip(),
                        "source": feed_name,
                        "source_type": "rss",
                        "matched_keyword": matched_keyword,
                        "published_at": published,
                        "story_hash": _hash_story(title, link),
                    }
                    stories.append(story)
                    logger.debug(f"  Matched: {title[:80]} [{matched_keyword}]")

        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_name}: {e}")
            continue

    exclude_kws = getattr(config, "EXCLUDE_KEYWORDS", [])
    filtered = []
    excluded_count = 0
    for story in stories:
        text = f"{story.get('title', '')} {story.get('summary', '')}".lower()
        if any(kw.lower() in text for kw in exclude_kws):
            excluded_count += 1
            continue
        filtered.append(story)

    if excluded_count > 0:
        logger.info(f"RSS Monitor: Excluded {excluded_count} irrelevant stories (sports/celebrity/etc.)")

    logger.info(f"RSS Monitor: Found {len(filtered)} women-welfare stories across {len(config.RSS_FEEDS)} feeds")
    return filtered


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    stories = fetch_rss_stories()
    for s in stories[:10]:
        print(f"[{s['source']}] {s['title']}")
        print(f"  Keyword: {s['matched_keyword']} | URL: {s['url'][:80]}")
        print()
