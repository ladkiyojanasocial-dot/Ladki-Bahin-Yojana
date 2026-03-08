"""
Coverage planner for guaranteed scheme-angle coverage and missed-topic recovery.
"""
from datetime import datetime, timedelta
import hashlib

from detection.scheme_registry import get_registry, DEFAULT_ANGLES, build_angle_topic


MAX_RECENT_TOPICS = 200


def _recent_topic_set(recent_topics):
    out = set()
    for t in recent_topics or []:
        topic = (t or "").strip().lower()
        if topic:
            out.add(topic)
    return out


def _build_topic_row(scheme, angle, score, reason):
    topic = build_angle_topic(scheme, angle)
    story_hash = hashlib.sha256(f"{scheme['id']}|{angle}|{topic}".encode("utf-8")).hexdigest()[:16]
    return {
        "topic": topic,
        "score": score,
        "factors": [reason, f"coverage angle: {angle}", f"scheme: {scheme['name']}"] ,
        "stories": [],
        "sources": ["Coverage Planner"],
        "top_url": "",
        "matched_keyword": scheme["name"],
        "story_count": 0,
        "story_hash": story_hash,
        "scheme_id": scheme["id"],
        "content_angle": angle,
        "coverage_source": "planner",
        "lang": "en",
    }


def build_coverage_topics(conn, max_items=6, recent_topics=None):
    """
    Build high-priority scheme topics when real-time spikes are low or coverage is missing.
    Prefers stale/missing scheme-angle combinations.
    """
    rows = []
    recent_set = _recent_topic_set(recent_topics)
    now = datetime.utcnow()
    schemes = sorted(get_registry(), key=lambda x: x.get("priority", 0), reverse=True)

    for scheme in schemes:
        for angle in DEFAULT_ANGLES:
            coverage = conn.execute(
                """SELECT last_generated_at, last_published_at
                   FROM content_coverage
                   WHERE scheme_id = ? AND content_angle = ?""",
                (scheme["id"], angle),
            ).fetchone()

            stale_hours = 999
            reason = "missing coverage"
            if coverage and coverage[0]:
                try:
                    last_generated = datetime.fromisoformat(str(coverage[0]).replace("Z", ""))
                    stale_hours = max(0, int((now - last_generated).total_seconds() // 3600))
                    reason = f"stale coverage ({stale_hours}h old)"
                except Exception:
                    stale_hours = 999
            if coverage and coverage[1]:
                try:
                    last_published = datetime.fromisoformat(str(coverage[1]).replace("Z", ""))
                    pub_hours = max(0, int((now - last_published).total_seconds() // 3600))
                    stale_hours = min(stale_hours, pub_hours)
                    reason = f"last publish {pub_hours}h ago"
                except Exception:
                    pass

            # Base score: scheme priority + freshness urgency + angle intent value
            intent_bonus = 0
            if angle in ("installment_update", "status_check", "ekyc_update"):
                intent_bonus = 18
            elif angle in ("eligibility", "apply_process", "rejection_fixes"):
                intent_bonus = 12
            score = (scheme.get("priority", 1) * 7) + min(stale_hours, 120) * 0.4 + intent_bonus

            rows.append({
                "scheme": scheme,
                "angle": angle,
                "score": round(score, 1),
                "reason": reason,
            })

    rows.sort(key=lambda x: x["score"], reverse=True)

    planned = []
    for row in rows:
        if len(planned) >= max_items:
            break
        topic = build_angle_topic(row["scheme"], row["angle"])
        if topic.lower() in recent_set:
            continue
        planned.append(_build_topic_row(row["scheme"], row["angle"], row["score"], row["reason"]))

    return planned


def build_refresh_topics(conn, max_items=3):
    """
    Build refresh topics for already published content that needs periodic update.
    """
    rows = conn.execute(
        """SELECT scheme_id, content_angle, last_published_at
           FROM content_coverage
           WHERE last_published_at IS NOT NULL
           ORDER BY last_published_at ASC"""
    ).fetchall()
    if not rows:
        return []

    schemes = {s["id"]: s for s in get_registry()}
    out = []
    now = datetime.utcnow()
    for row in rows:
        scheme = schemes.get(row["scheme_id"])
        if not scheme:
            continue
        angle = row["content_angle"] or "latest_news"
        try:
            last_pub = datetime.fromisoformat(str(row["last_published_at"]).replace("Z", ""))
        except Exception:
            continue
        if now - last_pub < timedelta(days=10):
            continue
        score = scheme.get("priority", 1) * 6 + min((now - last_pub).days, 30)
        out.append(_build_topic_row(scheme, angle, score, "scheduled freshness refresh"))
        if len(out) >= max_items:
            break
    return out


