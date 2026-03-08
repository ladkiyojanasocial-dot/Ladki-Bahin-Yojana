"""
Google Trends Monitor - Tracks rising search queries related to Indian Agriculture.
"""
import logging
import time
from datetime import datetime

from pytrends.request import TrendReq

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from detection.scheme_registry import get_trends_keywords

logger = logging.getLogger(__name__)


def _build_keyword_batches(keywords, batch_size=5):
    for i in range(0, len(keywords), batch_size):
        yield keywords[i:i + batch_size]


def _rotating_keywords(all_keywords, limit):
    if not all_keywords:
        return []
    hour = datetime.utcnow().hour
    start = (hour * 3) % len(all_keywords)
    ring = all_keywords[start:] + all_keywords[:start]
    return ring[:limit]


def fetch_trending_queries():
    trends = []

    try:
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 30))
    except Exception as e:
        logger.error(f"Failed to initialize pytrends: {e}")
        return trends

    registry_keywords = get_trends_keywords(limit=getattr(config, "TRENDS_KEYWORDS_MAX", 40))
    fallback_keywords = config.ALL_KEYWORDS[:20]
    candidate_keywords = registry_keywords or fallback_keywords
    core_keywords = _rotating_keywords(candidate_keywords, getattr(config, "TRENDS_KEYWORDS_PER_CYCLE", 25))

    for batch in _build_keyword_batches(core_keywords):
        try:
            logger.info(f"Checking Google Trends for: {batch}")
            pytrends.build_payload(batch, cat=0, timeframe='now 7-d', geo=config.TRENDS_GEO)
            interest_df = pytrends.interest_over_time()
            if interest_df is not None and not interest_df.empty:
                for keyword in batch:
                    if keyword in interest_df.columns:
                        values = interest_df[keyword].tolist()
                        if len(values) >= 2:
                            current = values[-1]
                            avg_overall = sum(values) / len(values)
                            prior = max(1, values[-2])
                            velocity = current / prior
                            is_rising = current > avg_overall * 1.35 or velocity >= 1.4

                            trends.append({
                                "keyword": keyword,
                                "current_interest": int(current),
                                "avg_interest": round(avg_overall, 1),
                                "is_rising": is_rising,
                                "spike_ratio": round(current / max(avg_overall, 1), 2),
                                "velocity": round(velocity, 2),
                                "source": "google_trends",
                                "source_type": "trends",
                                "recorded_at": datetime.utcnow(),
                            })

                            if is_rising:
                                logger.info(f"  RISING: '{keyword}' current={current} avg={avg_overall:.0f} vel={velocity:.2f}")

            time.sleep(4)

        except Exception as e:
            logger.warning(f"Google Trends error for batch {batch}: {e}")
            time.sleep(8)
            continue

    # Related rising queries for top 3 core keywords
    for top_keyword in core_keywords[:3]:
        try:
            pytrends.build_payload([top_keyword], cat=0, timeframe='now 7-d', geo=config.TRENDS_GEO)
            related = pytrends.related_queries()

            if related and top_keyword in related:
                rising_df = related[top_keyword].get("rising")
                if rising_df is not None and not rising_df.empty:
                    for _, row in rising_df.head(8).iterrows():
                        query = str(row.get("query", "")).strip()
                        value = row.get("value", 0)
                        if not query:
                            continue

                        query_lower = query.lower()
                        if any(ex_kw.lower() in query_lower for ex_kw in getattr(config, "EXCLUDE_KEYWORDS", [])):
                            continue

                        trends.append({
                            "keyword": query,
                            "current_interest": int(value) if isinstance(value, (int, float)) else 0,
                            "avg_interest": 0,
                            "is_rising": True,
                            "spike_ratio": 0,
                            "velocity": 0,
                            "source": "google_trends_related",
                            "source_type": "trends",
                            "recorded_at": datetime.utcnow(),
                        })
        except Exception as e:
            logger.warning(f"Related queries error for {top_keyword}: {e}")

    logger.info(f"Trends Monitor: {len(trends)} trend points, {sum(1 for t in trends if t['is_rising'])} rising")
    return trends


def get_realtime_trending():
    realtime_trends = []

    try:
        pytrends = TrendReq(hl='en-US', tz=0)
        trending = pytrends.trending_searches(pn='india')
        watchlist = set(kw.lower() for kw in (get_trends_keywords(limit=140) + config.ALL_KEYWORDS))

        if trending is not None and not trending.empty:
            for _, row in trending.iterrows():
                query = str(row[0]).strip()
                ql = query.lower()

                if any(ex_kw.lower() in ql for ex_kw in getattr(config, "EXCLUDE_KEYWORDS", [])):
                    continue

                matched = None
                for kw in watchlist:
                    if kw in ql or any(part in ql for part in kw.split() if len(part) > 3):
                        matched = kw
                        break

                if matched:
                    realtime_trends.append({
                        "keyword": query,
                        "source": "google_trending",
                        "source_type": "realtime_trends",
                        "is_rising": True,
                        "matched_keyword": matched,
                        "recorded_at": datetime.utcnow(),
                    })

    except Exception as e:
        logger.warning(f"Real-time trending error: {e}")

    return realtime_trends
