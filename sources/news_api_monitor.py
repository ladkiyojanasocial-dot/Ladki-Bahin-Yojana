"""
NewsAPI Monitor - Fetches top headlines and rotating scheme queries.
"""
import json
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from newsapi import NewsApiClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from detection.scheme_registry import get_trends_keywords

logger = logging.getLogger(__name__)
_BACKOFF_FILE = Path(os.path.dirname(os.path.dirname(__file__))) / "newsapi_backoff.json"
_BACKOFF_HOURS = 12


def _hash_story(title, url):
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _key_id(api_key):
    return hashlib.sha256((api_key or "").encode()).hexdigest()[:12]


def _load_backoff_state():
    try:
        if not _BACKOFF_FILE.exists():
            return {}
        payload = json.loads(_BACKOFF_FILE.read_text(encoding="utf-8-sig")) or {}
        keys = payload.get("keys")
        return keys if isinstance(keys, dict) else {}
    except Exception:
        return {}


def _save_backoff_state(state):
    try:
        _BACKOFF_FILE.write_text(
            json.dumps({"keys": state}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"NewsAPI backoff state save failed: {e}")


def _cleanup_backoff_state(now):
    state = _load_backoff_state()
    active = {}
    for key_id, until_value in state.items():
        try:
            until_dt = datetime.fromisoformat(until_value)
            if until_dt > now:
                active[key_id] = until_value
        except Exception:
            continue
    if active != state:
        if active:
            _save_backoff_state(active)
        else:
            try:
                _BACKOFF_FILE.unlink(missing_ok=True)
            except Exception:
                pass
    return active


def _mark_key_rate_limited(api_key):
    state = _cleanup_backoff_state(datetime.utcnow())
    until_dt = datetime.utcnow() + timedelta(hours=_BACKOFF_HOURS)
    state[_key_id(api_key)] = until_dt.isoformat()
    _save_backoff_state(state)
    return until_dt


def _available_newsapi_clients():
    keys = getattr(config, "NEWS_API_KEYS", []) or []
    if not keys:
        return []

    now = datetime.utcnow()
    backoff_state = _cleanup_backoff_state(now)
    available = []
    cooling = []
    for idx, api_key in enumerate(keys):
        kid = _key_id(api_key)
        until_value = backoff_state.get(kid)
        if until_value:
            try:
                cooling.append((idx + 1, datetime.fromisoformat(until_value)))
            except Exception:
                pass
            continue
        try:
            available.append((idx + 1, api_key, NewsApiClient(api_key=api_key)))
        except Exception as e:
            logger.error(f"Failed to initialize NewsAPI client #{idx + 1}: {e}")

    if not available and cooling:
        soonest = min(dt for _, dt in cooling)
        logger.warning(
            f"NewsAPI all keys are cooling down until {soonest.isoformat(timespec='minutes')} UTC; skipping requests this cycle"
        )
    return available


def _build_rotating_queries():
    base_queries = [
        "women welfare scheme india",
        "women empowerment yojana india",
        "mahila scheme india",
        "girl child scheme india",
        "women benefit portal india",
        "women entrepreneurship scheme india",
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

    max_q = getattr(config, "NEWSAPI_ROTATING_QUERY_COUNT", 1)
    hour = datetime.utcnow().hour
    start = (hour * 2) % max(len(dedup), 1)
    ring = dedup[start:] + dedup[:start]
    return ring[:max_q]


def _newsapi_call(clients, fn_name, **kwargs):
    last_error = None
    for key_num, api_key, client in clients:
        try:
            fn = getattr(client, fn_name)
            result = fn(**kwargs)
            return result, False
        except Exception as e:
            message = str(e)
            if "rateLimited" in message:
                until_dt = _mark_key_rate_limited(api_key)
                logger.warning(
                    f"NewsAPI key {key_num} rate limited; cooling down until {until_dt.isoformat(timespec='minutes')} UTC"
                )
                last_error = e
                continue
            raise
    if last_error:
        return None, True
    return None, False


def fetch_news_headlines():
    stories = []
    clients = _available_newsapi_clients()
    if not clients:
        return stories

    rate_limited = False

    try:
        logger.info(f"NewsAPI: Fetching top headlines for women welfare in India using {len(clients)} key(s)")
        top, rate_limited = _newsapi_call(
            clients,
            "get_top_headlines",
            q="women welfare OR mahila yojana OR ladli behna",
            country="in",
            page_size=20,
        )
        if top and top.get("status") == "ok":
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
                    "matched_keyword": "women welfare",
                    "published_at": _parse_date(article.get("publishedAt")),
                    "story_hash": _hash_story(title, article.get("url", "")),
                    "image_url": article.get("urlToImage", ""),
                })
    except Exception as e:
        logger.error(f"NewsAPI top headlines error: {e}")

    search_queries = _build_rotating_queries()
    if rate_limited:
        logger.warning("NewsAPI rate limit reached across available keys; skipping query loop for this cycle")
        search_queries = []

    for query in search_queries:
        try:
            from_date = (datetime.utcnow() - timedelta(hours=30)).strftime("%Y-%m-%d")
            results, rate_limited = _newsapi_call(
                clients,
                "get_everything",
                q=query,
                language="en",
                sort_by="publishedAt",
                from_param=from_date,
                page_size=8,
            )
            if results and results.get("status") == "ok":
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
            if rate_limited:
                logger.warning("NewsAPI rate limit reached across available keys during query loop")
                break
        except Exception as e:
            logger.error(f"NewsAPI everything error for '{query}': {e}")
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
