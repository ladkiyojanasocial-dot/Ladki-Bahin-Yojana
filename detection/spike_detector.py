"""
Spike Detector - Aggregates stories from all sources, deduplicates,
calculates spike scores, and returns trending topics worth covering.
"""
import logging
import hashlib
from collections import defaultdict
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from detection.scheme_registry import find_best_scheme, infer_content_angle
from detection.language_router import detect_topic_language
from database.db import (
    get_connection, is_story_seen, add_story, record_keyword_mention,
    get_keyword_baseline
)

logger = logging.getLogger(__name__)

OFFICIAL_SOURCE_HINTS = (
    "pib", "gov", "icar", "agriculture", "ministry", "state portal"
)
HIGH_INTENT_TERMS = (
    "installment", "kist", "status", "ekyc", "eligibility", "last date",
    "deadline", "apply", "registration", "beneficiary"
)


def _cluster_stories(stories):
    clusters = defaultdict(list)

    for story in stories:
        title_words = set(story["title"].lower().split())
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                      "to", "for", "of", "with", "and", "or", "but", "not", "this",
                      "that", "it", "as", "by", "from", "has", "have", "had", "will",
                      "be", "been", "can", "could", "would", "should", "do", "does"}
        key_words = title_words - stop_words

        best_match = None
        best_score = 0

        for cluster_key in clusters:
            cluster_words = set(cluster_key.split("|"))
            overlap = len(key_words & cluster_words)
            score = overlap / max(len(key_words | cluster_words), 1)
            if score > best_score and score > 0.3:
                best_match = cluster_key
                best_score = score

        if best_match:
            clusters[best_match].append(story)
        else:
            cluster_key = "|".join(sorted(key_words)[:8])
            clusters[cluster_key].append(story)

    return clusters


def _calculate_spike_score(cluster_stories, conn):
    score = 0.0
    factors = []

    unique_sources = set(s["source"] for s in cluster_stories)
    source_count = len(unique_sources)
    score += source_count * 15
    factors.append(f"{source_count} sources")

    source_types = set(s.get("source_type", "unknown") for s in cluster_stories)
    if len(source_types) > 1:
        score += len(source_types) * 12
        factors.append(f"{len(source_types)} source types")

    now = datetime.utcnow()
    for story in cluster_stories:
        pub = story.get("published_at", now)
        if isinstance(pub, datetime):
            hours_old = (now - pub).total_seconds() / 3600
            if hours_old < 2:
                score += 20
            elif hours_old < 6:
                score += 10

    # Trends velocity boost
    spike_ratios = [float(s.get("spike_ratio", 0) or 0) for s in cluster_stories]
    max_ratio = max(spike_ratios) if spike_ratios else 0
    if max_ratio >= 2:
        boost = min(30, max_ratio * 5)
        score += boost
        factors.append(f"trend velocity {max_ratio:.1f}x")

    for story in cluster_stories:
        if story.get("is_rising"):
            score += 25
            factors.append("trending on Google")
            break

    high_value_keywords = getattr(config, "HIGH_VALUE_AGRI_KEYWORDS", HIGH_INTENT_TERMS)
    for story in cluster_stories:
        text = (story.get("title", "") + " " + story.get("summary", "")).lower()
        matched = [kw for kw in high_value_keywords if kw.lower() in text]
        if matched:
            score += min(20, 6 + len(matched) * 3)
            factors.append("high-intent search intent")
            break

    # Official source trust boost
    trusted_hits = 0
    for story in cluster_stories:
        source_blob = f"{story.get('source', '')} {story.get('url', '')}".lower()
        if any(h in source_blob for h in OFFICIAL_SOURCE_HINTS):
            trusted_hits += 1
    if trusted_hits:
        trust_score = min(20, trusted_hits * 4)
        score += trust_score
        factors.append("official-source signal")

    for story in cluster_stories:
        kw = story.get("matched_keyword", "")
        if kw:
            baseline_avg, samples = get_keyword_baseline(conn, kw)
            if samples > 0 and baseline_avg > 0:
                current_mentions = len(cluster_stories)
                ratio = current_mentions / baseline_avg
                if ratio >= config.SPIKE_THRESHOLD:
                    score += ratio * 10
                    factors.append(f"keyword spike {ratio:.1f}x")

    return round(score, 1), factors


def _is_excluded(text):
    text_lower = text.lower()
    for kw in getattr(config, "EXCLUDE_KEYWORDS", []):
        if kw.lower() in text_lower:
            return True
    return False


def _suggest_article_title(cluster_stories):
    import re
    combined = " ".join(s.get("title", "") + " " + s.get("summary", "") for s in cluster_stories)
    combined_lower = combined.lower()
    matched_kw = ""
    for s in cluster_stories:
        if s.get("matched_keyword"):
            matched_kw = s["matched_keyword"]
            break

    instal_match = re.search(r"(\d+)(?:st|nd|rd|th)?\s*instal?l?ment", combined_lower, re.I)
    if instal_match and ("pm kisan" in combined_lower or "pm-kisan" in combined_lower or matched_kw and "kisan" in matched_kw.lower()):
        num = instal_match.group(1)
        return f"PM Kisan {num}th Installment Date and Status {datetime.utcnow().year}"

    if "ekyc" in combined_lower or "e-kyc" in combined_lower:
        if "pm kisan" in combined_lower or (matched_kw and "kisan" in matched_kw.lower()):
            return f"PM Kisan eKYC Deadline {datetime.utcnow().year}: How to Complete and Check Status"
        return f"Farmer Scheme eKYC Update {datetime.utcnow().year}: Process and Last Date"

    if "status check" in combined_lower or "check status" in combined_lower:
        if "pm kisan" in combined_lower or (matched_kw and "kisan" in matched_kw.lower()):
            return f"PM Kisan Status Check {datetime.utcnow().year}: Payment and Beneficiary Status"
        if "pmfby" in combined_lower or "fasal bima" in combined_lower:
            return "PMFBY Claim Status Check: How to Check Crop Insurance Status"

    if "enrollment" in combined_lower or "enrolment" in combined_lower or "registration" in combined_lower:
        if "pmfby" in combined_lower or "rabi" in combined_lower or "kharif" in combined_lower:
            return "PMFBY Rabi/Kharif Enrollment: Last Date and How to Apply"
        if "enam" in combined_lower or "e-nam" in combined_lower:
            return "e-NAM Registration: Mandi Registration and Price Guide"

    if "new scheme" in combined_lower or "launched" in combined_lower or "announced" in combined_lower:
        for s in cluster_stories:
            t = s.get("title", "")
            if 15 < len(t) < 80:
                return t

    return None


def detect_spikes(all_stories, trends_data=None):
    conn = get_connection()

    combined = list(all_stories)
    if trends_data:
        for trend in trends_data:
            if trend.get("is_rising"):
                combined.append({
                    "title": f"Rising search: {trend['keyword']}",
                    "summary": f"Google Trends shows '{trend['keyword']}' rising ({trend.get('spike_ratio', 0)}x)",
                    "url": f"https://trends.google.com/trends/explore?q={trend['keyword'].replace(' ', '+')}",
                    "source": trend.get("source", "Google Trends"),
                    "source_type": "trends",
                    "matched_keyword": trend["keyword"],
                    "published_at": trend.get("recorded_at", datetime.utcnow()),
                    "story_hash": hashlib.sha256(trend["keyword"].encode()).hexdigest()[:16],
                    "is_rising": True,
                    "spike_ratio": trend.get("spike_ratio", 0),
                })

    filtered = []
    excluded_count = 0
    for story in combined:
        title = story.get("title", "")
        keyword = story.get("matched_keyword", "")
        if _is_excluded(title) or _is_excluded(keyword):
            excluded_count += 1
            continue
        filtered.append(story)

    if excluded_count > 0:
        logger.info(f"Spike Detector: Excluded {excluded_count} irrelevant stories")
    combined = filtered

    new_stories = []
    for story in combined:
        if not is_story_seen(conn, story["story_hash"], config.DEDUP_WINDOW_HOURS):
            new_stories.append(story)
            add_story(conn, story["story_hash"], story["title"],
                      story["source"], story.get("url", ""),
                      story.get("matched_keyword", ""))

    if not new_stories:
        logger.info("Spike Detector: No new stories found")
        conn.close()
        return []

    logger.info(f"Spike Detector: Processing {len(new_stories)} new stories")

    keyword_counts = defaultdict(int)
    for story in new_stories:
        kw = story.get("matched_keyword", "")
        if kw:
            keyword_counts[kw] += 1
    for kw, count in keyword_counts.items():
        record_keyword_mention(conn, kw, "combined", count)

    clusters = _cluster_stories(new_stories)

    trending_topics = []
    min_score = getattr(config, "SPIKE_MIN_SCORE", 40)
    breaking_score = getattr(config, "BREAKING_SPIKE_SCORE", 95)

    for _, cluster_stories in clusters.items():
        score, factors = _calculate_spike_score(cluster_stories, conn)

        if score >= min_score:
            best_story = max(cluster_stories, key=lambda s: len(s["title"]))
            suggested = _suggest_article_title(cluster_stories)
            topic_title = suggested if suggested else best_story["title"]
            story_hash = hashlib.sha256((topic_title + best_story.get("url", "")).encode()).hexdigest()[:16]

            scheme = find_best_scheme(f"{topic_title} {best_story.get('matched_keyword', '')}")
            angle = infer_content_angle(topic_title)
            lang = detect_topic_language(topic_title, cluster_stories, best_story.get("matched_keyword", ""))

            trending_topics.append({
                "topic": topic_title,
                "score": score,
                "factors": factors,
                "stories": cluster_stories,
                "sources": list(set(s["source"] for s in cluster_stories)),
                "top_url": best_story.get("url", ""),
                "matched_keyword": best_story.get("matched_keyword", ""),
                "story_count": len(cluster_stories),
                "story_hash": story_hash,
                "scheme_id": scheme["id"] if scheme else "",
                "content_angle": angle,
                "lang": lang,
                "is_breaking": score >= breaking_score,
            })

    trending_topics.sort(key=lambda x: x["score"], reverse=True)

    conn.close()
    logger.info(f"Spike Detector: Identified {len(trending_topics)} trending topics")
    return trending_topics




