"""
Women Empowerment Alerts Agent â€” Main Entry Point

Orchestrates the detection â†’ notification â†’ writing â†’ publishing pipeline.
Runs on a configurable schedule (default: every 60 minutes).

Usage:
    python main.py              # Run the agent loop
    python main.py --once       # Run a single scan and exit
    python main.py --test       # Test all connections
"""
import argparse
import logging
import time
import sys
import os
import json
from datetime import datetime


# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

import config
from sources.rss_monitor import fetch_rss_stories
from sources.trends_monitor import fetch_trending_queries, get_realtime_trending
from sources.news_api_monitor import fetch_news_headlines
from detection.spike_detector import detect_spikes
from detection.coverage_planner import build_coverage_topics, build_refresh_topics
from detection.scheme_registry import find_best_scheme, infer_content_angle
from writer.quality_gate import validate_article_for_publish
from notifications.telegram_bot import (
    send_trending_alert, send_simple_message, send_status_update,
    send_article_preview, send_publish_confirmation, send_generating_status,
    send_quality_gate_decision,
    send_image_preview, get_updates, answer_callback_query, test_connection
)
from database.db import get_connection, cleanup_old_data, mark_notified, record_notification, save_topic_to_cache, get_topic_from_cache, mark_content_generated, mark_content_published
from writer.article_generator import generate_article
from publisher.wordpress_client import create_post
from publisher.image_handler import generate_featured_image
from gemini_client import generate_content_with_fallback

# â€”â€” Global state for command handler â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
_latest_topics = []       # Most recent trending topics from last scan
_pending_article = None   # Article awaiting approval
_pending_image_path = None  # Featured image awaiting approval
_update_offset = None     # Telegram getUpdates offset
_gemini_quota_exhausted = False  # Set True when Gemini daily quota is hit
_article_attempted_this_run = False  # Limit one article generation per --once run (avoids duplicate failures)
_publish_in_progress = False  # Prevent duplicate /approve callbacks from repeated publish attempts
_state_version = 2


def _build_state_payload():
    return {
        "state_version": _state_version,
        "app_namespace": getattr(config, "APP_STATE_NAMESPACE", "ladki-bahin-agent"),
        "article": _pending_article,
        "image_path": _pending_image_path,
        "update_offset": _update_offset,
    }


def save_pending_state():
    """Save pending article, image path, and telegram offset to disk."""
    state = _build_state_payload()
    try:
        with open("pending_state.json", "w", encoding="utf-8") as f:
            json.dump(state, f, default=str)
    except Exception as e:
        logger.error(f"Failed to save pending state: {e}")


def load_pending_state():
    """Load pending article, image path, and telegram offset from disk."""
    global _pending_article, _pending_image_path, _update_offset
    try:
        if os.path.exists("pending_state.json"):
            with open("pending_state.json", "r", encoding="utf-8-sig") as f:
                state = json.load(f)
                if state.get("state_version") != _state_version:
                    _pending_article = None
                    _pending_image_path = None
                    _update_offset = state.get("update_offset")
                    save_pending_state()
                    return False
                if state.get("app_namespace") != getattr(config, "APP_STATE_NAMESPACE", "ladki-bahin-agent"):
                    _pending_article = None
                    _pending_image_path = None
                    _update_offset = state.get("update_offset")
                    save_pending_state()
                    return False
                _pending_article = state.get("article")
                _pending_image_path = state.get("image_path")
                _update_offset = state.get("update_offset")
                if _pending_image_path and not os.path.exists(_pending_image_path):
                    _pending_image_path = None
                if not isinstance(_pending_article, dict) or not _pending_article.get("title"):
                    _pending_article = None
                    save_pending_state()
                    return False
                return True
    except Exception as e:
        logger.error(f"Failed to load pending state: {e}")
    return False

# â€”â€” Logging Setup â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), config.LOG_FILE),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger("WomenEmpowermentAgent")


def run_scan():
    """
    Execute a single scan cycle:
    1. Fetch stories from all sources
    2. Detect spikes
    3. Send Telegram alerts for trending topics
    """
    logger.info("=" * 60)
    logger.info(f"ðŸ” Starting scan at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    all_stories = []
    trends_data = []

    # â€”â€” Step 1: Fetch from all sources â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
    # RSS Feeds
    try:
        logger.info("ðŸ“¡ Fetching RSS feeds...")
        rss_stories = fetch_rss_stories()
        all_stories.extend(rss_stories)
        logger.info(f"   RSS: {len(rss_stories)} stories")
    except Exception as e:
        logger.error(f"RSS Monitor failed: {e}")

    # NewsAPI
    try:
        logger.info("ðŸ“° Fetching NewsAPI headlines...")
        news_stories = fetch_news_headlines()
        all_stories.extend(news_stories)
        logger.info(f"   NewsAPI: {len(news_stories)} stories")
    except Exception as e:
        logger.error(f"NewsAPI Monitor failed: {e}")

    # Google Trends
    try:
        logger.info("ðŸ“ˆ Checking Google Trends...")
        trends_data = fetch_trending_queries()
        logger.info(f"   Trends: {len(trends_data)} data points")
    except Exception as e:
        logger.error(f"Trends Monitor failed: {e}")

    # Real-time trending searches
    try:
        logger.info("âš¡ Checking real-time trending searches...")
        realtime = get_realtime_trending()
        # Add real-time trends as stories
        for rt in realtime:
            all_stories.append({
                "title": f"Trending: {rt['keyword']}",
                "summary": f"'{rt['keyword']}' is currently trending on Google in India",
                "url": f"https://trends.google.com/trends/explore?q={rt['keyword'].replace(' ', '+')}",
                "source": "Google Trending",
                "source_type": "realtime_trends",
                "matched_keyword": rt.get("matched_keyword", rt["keyword"]),
                "published_at": datetime.utcnow(),
                "story_hash": f"rt_{rt['keyword'][:20].replace(' ', '_')}",
                "is_rising": True,
            })
        logger.info(f"   Real-time: {len(realtime)} women-scheme-related trends")
    except Exception as e:
        logger.error(f"Real-time Trends failed: {e}")

    # â€”â€” Step 2: Detect spikes â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
    logger.info(f"\nðŸ”¬ Analyzing {len(all_stories)} total stories...")
    trending_topics = detect_spikes(all_stories, trends_data)

    # Helpers for topic rotation (avoid suggesting same topic many cycles in a row)
    RECENT_TOPICS_FILE = "recently_suggested_topics.json"
    RECENT_TOPICS_MAX = 30  # Keep longer memory to avoid repeats across 100+ ideas

    def _load_recent_suggested():
        try:
            if os.path.exists(RECENT_TOPICS_FILE):
                with open(RECENT_TOPICS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_recent_suggested(recent):
        try:
            with open(RECENT_TOPICS_FILE, "w", encoding="utf-8") as f:
                json.dump(recent[-RECENT_TOPICS_MAX:], f)
        except Exception as e:
            logger.debug(f"Could not save recent topics: {e}")

    # When few or no spike topics, inject 2-3 priority content ideas covering DIVERSE angles
    # (eligibility, eKYC, status check, rule change, installment, guide, etc.)
    content_ideas = getattr(config, "CONTENT_IDEAS", [])
    IDEAS_TO_INJECT = 3 if len(trending_topics) == 0 else 2  # More ideas when no real news
    if content_ideas and len(trending_topics) < 2:
        import hashlib
        import random
        recent = _load_recent_suggested()
        # Prefer ideas not recently suggested
        available = [i for i in content_ideas if (i.get("topic") or "").strip() not in recent]
        if len(available) < IDEAS_TO_INJECT:
            # Pool is nearly exhausted â€” reset rotation but keep last few to avoid immediate repeats
            available = content_ideas
            recent = recent[-5:] if len(recent) > 5 else []
        # Shuffle using hour-based seed so each cycle within the same day picks different topics
        now = datetime.utcnow()
        seed = int(now.strftime("%Y%m%d%H")) + len(recent)
        rng = random.Random(seed)
        rng.shuffle(available)
        # Try to pick ideas from DIFFERENT schemes (avoid repeating same scheme ideas in one cycle)
        injected_keywords = set()
        injected_count = 0
        for idea in available:
            if injected_count >= IDEAS_TO_INJECT:
                break
            kw = (idea.get("matched_keyword") or "").lower()
            # Skip if same scheme already picked this cycle (allow after all schemes exhausted)
            if kw in injected_keywords and injected_count < len(available):
                continue
            idea_hash = hashlib.sha256(("content_idea_" + idea["topic"]).encode()).hexdigest()[:16]
            trending_topics.append({
                "topic": idea["topic"],
                "score": 50.0 - injected_count,  # Slight score decrease for ordering
                "factors": ["priority content idea (scheme/installment/guide)"],
                "stories": [],
                "sources": ["Women Welfare editorial"],
                "top_url": "",
                "matched_keyword": idea.get("matched_keyword", "women welfare"),
                "story_count": 0,
                "story_hash": idea_hash,
            })
            recent.append(idea["topic"].strip())
            injected_keywords.add(kw)
            injected_count += 1
            logger.info(f"   ðŸ“Œ Injected priority topic #{injected_count}: {idea['topic'][:60]}...")
        _save_recent_suggested(recent)
        logger.info(f"   ðŸ“Œ Total injected: {injected_count} content ideas this cycle")

    # Coverage-first planner: guarantee scheme-angle coverage and missed-topic recovery.
    try:
        planner_conn = get_connection()
        recent_topics = _load_recent_suggested()
        coverage_needed = max(0, getattr(config, "MIN_COVERAGE_TOPICS_PER_CYCLE", 4) - len(trending_topics))
        if coverage_needed > 0:
            planner_topics = build_coverage_topics(planner_conn, max_items=coverage_needed, recent_topics=recent_topics)
            if planner_topics:
                trending_topics.extend(planner_topics)
                logger.info(f"   Coverage planner injected {len(planner_topics)} scheme-angle topics")
        refresh_topics = build_refresh_topics(planner_conn, max_items=getattr(config, "MAX_REFRESH_TOPICS_PER_CYCLE", 2))
        if refresh_topics:
            trending_topics.extend(refresh_topics)
            logger.info(f"   Freshness planner injected {len(refresh_topics)} refresh topics")
        planner_conn.close()
    except Exception as e:
        logger.error(f"Coverage planner failed: {e}")

    if not trending_topics:
        logger.info("âœ… No new trending topics detected this cycle.")
        # Always send a scan summary so user knows the agent is working
        send_simple_message(
            f"ðŸ“Š Scan complete ({datetime.now().strftime('%H:%M UTC')})\n"
            f"Stories found: {len(all_stories)}\n"
            f"Trending topics: 0\n"
            f"No alerts this cycle â€” all quiet."
        )
        return 0

    # Put less-recently-suggested topics first so default "Write Article" choice is fresh
    try:
        recent_set = set(_load_recent_suggested())
        trending_topics = sorted(
            trending_topics,
            key=lambda t: (1 if (t.get("topic") or "").strip() in recent_set else 0, -t.get("score", 0)),
        )
    except Exception:
        pass

    logger.info(f"ðŸ”¥ Found {len(trending_topics)} trending topics!")

    # â€”â€” Step 3: Send Telegram alerts â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”â€”
    conn = get_connection()
    alerts_sent = 0

    for topic in trending_topics[:8]:  # Max 8 alerts per cycle (increased for multi-idea injection)
        try:
            # Establish a single, consistent hash for the Telegram button AND the database cache
            story_hash = topic.get("story_hash")
            if not story_hash and topic.get("stories"):
                story_hash = topic["stories"][0].get("story_hash")
            
            if not story_hash:
                import hashlib
                story_hash = hashlib.md5(topic["topic"].encode()).hexdigest()
                
            topic["story_hash"] = story_hash

            logger.info(f"\nðŸ“± Sending alert: {topic['topic'][:80]}")
            logger.info(f"   Score: {topic['score']} | Sources: {', '.join(topic['sources'][:3])}")

            message_id = send_trending_alert(topic)

            if message_id:
                alerts_sent += 1
                # Record in database
                for story in topic.get("stories", []):
                    shash = story.get("story_hash", "")
                    if shash:
                        mark_notified(conn, shash)
                
                save_topic_to_cache(conn, story_hash, topic)
                record_notification(conn, story_hash, message_id)
                # Track suggested topic so we rotate and don't repeat same topic for many cycles
                rec = _load_recent_suggested()
                rec.append((topic.get("topic") or "").strip())
                _save_recent_suggested(rec)
                logger.info(f"   âœ… Alert sent (Telegram ID: {message_id})")
            else:
                logger.warning(f"   âš ï¸  Failed to send alert")

            # Small delay between messages to avoid Telegram rate limits
            time.sleep(1)

        except Exception as e:
            logger.error(f"Error sending alert for '{topic['topic'][:50]}': {e}")

    conn.close()
    logger.info(f"\nðŸ“Š Scan complete: {alerts_sent} alerts sent out of {len(trending_topics)} topics")

    # Store topics for command handler
    global _latest_topics
    _latest_topics = trending_topics
    
    # Save topics to disk for robustness across runs (especially if Telegram times out)
    try:
        with open("latest_topics.json", "w", encoding="utf-8") as f:
            json.dump(_latest_topics, f, default=str)
    except Exception as e:
        logger.error(f"Failed to save latest topics to disk: {e}")


    # Breaking mode: auto-start draft generation for highest urgency topic.
    try:
        if getattr(config, "AUTO_GENERATE_BREAKING", False) and not _pending_article:
            breaking = next((t for t in trending_topics if t.get("is_breaking")), None)
            if breaking:
                send_simple_message(
                    f"Breaking scheme update detected: {breaking.get('topic', '')[:120]}\nStarting auto-draft generation..."
                )
                _handle_write_article(breaking.get("story_hash"))
    except Exception as e:
        logger.error(f"Breaking auto-generation failed: {e}")
    return alerts_sent


def check_and_handle_commands():
    """
    Poll Telegram for incoming commands/button presses and handle them.
    Supports:
      - write_article (inline button or /write_article text)
      - approve / publish_live (inline button or /approve, /publish_live text)
      - ignore (inline button)
    """
    global _update_offset, _latest_topics, _pending_article, _pending_image_path

    updates = get_updates(offset=_update_offset)
    if not updates:
        return

    for update in updates:
        _update_offset = update["update_id"] + 1
        save_pending_state()

        # Handle inline button callback
        callback = update.get("callback_query")
        if callback:
            data = callback.get("data", "")
            callback_id = callback.get("id")
            logger.info(f"ðŸ“± Received callback: {data}")

            if data.startswith("write_"):
                answer_callback_query(callback_id, "âŒ› Checking topic...")
                if data == "write_article":
                    topic_hash = None
                else:
                    topic_hash = data.split("_", 1)[1] if "_" in data else None
                
                # Check if confirmation is required
                if getattr(config, "REQUIRE_ARTICLE_CONFIRMATION", True):
                    # Load topic to show in confirmation
                    topic = None
                    if topic_hash:
                        try:
                            conn = get_connection()
                            topic = get_topic_from_cache(conn, topic_hash)
                            conn.close()
                        except:
                            pass
                        if not topic and _latest_topics:
                            topic = next((t for t in _latest_topics if (t.get("story_hash") or "") == topic_hash), None)
                    
                    if not topic and _latest_topics:
                        topic = _latest_topics[0]
                    
                    if topic:
                        from notifications.telegram_bot import send_generation_confirmation
                        send_generation_confirmation(topic)
                    else:
                        send_simple_message("âš ï¸ Could not find topic details for confirmation.")
                else:
                    _handle_write_article(topic_hash)

            elif data.startswith("confirm_write_"):
                answer_callback_query(callback_id, "âœï¸ Starting generation...")
                topic_hash = data.split("_")[-1]
                if topic_hash == "none": topic_hash = None
                _handle_write_article(topic_hash)

            elif data == "cancel_write":
                answer_callback_query(callback_id, "âŒ Generation cancelled.")
                send_simple_message("âŒ Article generation cancelled.")

            elif data == "approve":
                answer_callback_query(callback_id, "âœ… Publishing as draft...")
                _handle_approve(status="draft")
            elif data == "publish_live":
                answer_callback_query(callback_id, "ðŸš€ Publishing live...")
                _handle_approve(status="publish")
            elif data == "quality_continue_draft":
                answer_callback_query(callback_id, "âœ… Continuing as draft...")
                _handle_approve(status="draft", bypass_quality_gate=True)
            elif data == "quality_continue_publish":
                answer_callback_query(callback_id, "ðŸš€ Continuing despite quality warnings...")
                _handle_approve(status="publish", bypass_quality_gate=True)
            elif data == "reject":
                answer_callback_query(callback_id, "ðŸ—‘ï¸ Article discarded.")
                _pending_article = None
                _pending_image_path = None
                save_pending_state()
                send_simple_message("ðŸ—‘ï¸ Article discarded.")
            elif data == "approve_image":
                answer_callback_query(callback_id, "âœ… Image approved!")
                send_simple_message("âœ… Image approved! It will be used as the featured image when you publish.")
            elif data == "regenerate_image":
                answer_callback_query(callback_id, "ðŸ”„ Regenerating image...")
                _handle_regenerate_image()
            elif data == "skip_image":
                answer_callback_query(callback_id, "ðŸš« Image skipped.")
                _pending_image_path = None
                save_pending_state()
                send_simple_message("ðŸš« Image skipped. Article will be published without a featured image.")
            elif data.startswith("publish_draft_"):
                post_id = data.split("_")[-1]
                answer_callback_query(callback_id, "ðŸš€ Making post live...")
                _handle_publish_draft(post_id)
            elif data == "ignore":
                answer_callback_query(callback_id, "ðŸ‘ Ignored.")
            continue

        # Handle text commands
        message = update.get("message", {})
        text = message.get("text", "").strip().lower()

        if text.startswith("/write_article"):
            _handle_write_article()
        elif text.startswith("/approve"):
            _handle_approve(status="draft")
        elif text.startswith("/publish_live"):
            _handle_approve(status="publish")
        elif text.startswith("/reject"):
            _pending_article = None
            _pending_image_path = None
            save_pending_state()
            send_simple_message("Article discarded.")
        elif text.startswith("/clear_pending"):
            _pending_article = None
            _pending_image_path = None
            save_pending_state()
            send_simple_message("âœ… Pending article cleared. You can generate a new one now.")


def _handle_write_article(topic_hash=None):
    """Generate an article for a specific topic, or the most recent one if no hash provided."""
    global _pending_article, _latest_topics, _gemini_quota_exhausted, _article_attempted_this_run

    # Only allow one article generation attempt per --once run (avoids multiple stale callbacks)
    if _article_attempted_this_run:
        logger.info("ðŸ•™ Skipping duplicate write_article â€” already attempted this run")
        send_simple_message("âœï¸ An article generation is already in progress or was just attempted. Please wait a moment.")
        return

    if _gemini_quota_exhausted:
        logger.info("ðŸ”‹ Skipping article generation â€” Gemini quota exhausted this cycle")
        send_simple_message("ðŸ”‹ Gemini API quota exhausted. Article generation paused until next cycle.")
        return

    if not getattr(config, "GEMINI_API_KEYS", None) or not config.GEMINI_API_KEYS:
        logger.error("No Gemini API key configured. Add GEMINI_API_KEYS to .env in the project root.")
        send_simple_message(
            "âŒ Gemini API key not set.\n\n"
            "Add GEMINI_API_KEYS=key1,key2 to a .env file in the project folder (same folder as main.py), then run again."
        )
        return

    # Don't start a new one if an article is already pending review
    if _pending_article or load_pending_state():
        title = (_pending_article or {}).get("title", "Unknown")
        send_simple_message(
            f"âš ï¸ An article is already pending review: '{title}'\n\n"
            "Please âœ… Approve or ðŸ—‘ï¸ Reject it before generating a new one.\n\n"
            "If you don't see the article preview, send /clear_pending to discard and start fresh."
        )
        return

    topic = None
    
    # Prioritize loading the specific topic requested via Telegram callback (supports older alerts)
    if topic_hash:
        try:
            conn = get_connection()
            topic = get_topic_from_cache(conn, topic_hash)
            conn.close()
            if topic:
                logger.info(f"Loaded specific topic {topic_hash} from cache.")
            else:
                topic = next((t for t in _latest_topics if (t.get("story_hash") or "") == topic_hash), None)
                if topic:
                    logger.info(f"Loaded specific topic {topic_hash} from in-memory latest topics.")
                else:
                    logger.warning(f"Topic hash {topic_hash} not found in cache.")
                    send_simple_message("âš ï¸ This alert is too old (cache expired) or the topic record is no longer available.")
                    return
        except Exception as e:
            logger.error(f"Error loading topic {topic_hash} from cache: {e}")

    # Fallbacks if it wasn't a callback or the cache was cleared
    if not topic:
        if _latest_topics:
            topic = _latest_topics[0]
        else:
            # Reconstruct from disk if running in isolated environment (e.g., GitHub Actions)
            # We use a local JSON file now because DB 'notifications_sent' might be empty if Telegram timed out.
            try:
                if os.path.exists("latest_topics.json"):
                    with open("latest_topics.json", "r", encoding="utf-8") as f:
                        saved_topics = json.load(f)
                        if saved_topics and len(saved_topics) > 0:
                            topic = saved_topics[0]
                            _latest_topics = saved_topics  # Restore to memory
            except Exception as e:
                logger.error(f"Error reading last topics from disk: {e}")
                
            # Fallback to DB (legacy approach) if JSON is missing
            if not topic:
                try:
                    conn = get_connection()
                    row = conn.execute("""
                        SELECT s.title, s.source, s.url, s.keywords, s.story_hash
                        FROM notifications_sent n
                        JOIN seen_stories s ON n.story_hash = s.story_hash
                        ORDER BY n.sent_at DESC LIMIT 1
                    """).fetchone()
                    conn.close()
                    
                    if row:
                        topic = {
                            "topic": row["title"],
                            "matched_keyword": row["keywords"],
                            "top_url": row["url"],
                            "stories": [{"title": row["title"], "source": row["source"], "url": row["url"], "summary": row["title"]}]
                        }
                except Exception as e:
                    logger.error(f"Error reading last topic from DB: {e}")

    if not topic:
        send_simple_message("âš ï¸ No trending topics found in memory or database. Wait for the next scan.")
        return

    _article_attempted_this_run = True

    logger.info(f"ðŸ“ Generating article for: {topic.get('topic', 'Unknown')}")

    send_generating_status(topic["topic"])

    try:
        article = generate_article(topic)
        if article:
            article["matched_keyword"] = topic.get("matched_keyword", "")  # For RankMath focus keyword
            article["source_url"] = topic.get("top_url") or (topic.get("stories") or [{}])[0].get("url") or ""
            scheme_id = topic.get("scheme_id") or ""
            content_angle = topic.get("content_angle") or ""
            if not scheme_id:
                scheme = find_best_scheme(f"{topic.get('topic', '')} {article.get('matched_keyword', '')}")
                scheme_id = (scheme or {}).get("id", "")
            if not content_angle:
                content_angle = infer_content_angle(topic.get("topic", ""))
            article["scheme_id"] = scheme_id
            article["content_angle"] = content_angle
            if scheme_id and content_angle:
                try:
                    conn_cov = get_connection()
                    mark_content_generated(conn_cov, scheme_id, content_angle, topic.get("topic", ""))
                    conn_cov.close()
                except Exception as cov_err:
                    logger.warning(f"Coverage generated tracking failed: {cov_err}")
            _pending_article = article
            send_article_preview(article)
            logger.info(f"âœ… Article preview sent: {article['title']}")
            save_pending_state()
            # Auto-generate featured image (Gemini Flash â†’ source image â†’ Pollinations â†’ Imagen â†’ placeholder)
            if not getattr(config, "SKIP_AI_IMAGE", False):
                _generate_and_preview_image(article.get("title", ""), article.get("source_url"))
            else:
                send_simple_message("ðŸ–¼ï¸ Image skipped (SKIP_AI_IMAGE=enabled). You can approve the article without a featured image.")
        else:
            send_simple_message(
                "âŒ Article generation failed (Gemini returned empty or output could not be parsed). "
                "Check agent logs for details or try again."
            )
    except Exception as e:
        error_str = str(e)
        logger.error(f"Article generation error: {e}")
        # If quota is exhausted, set the flag to prevent further attempts
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            _gemini_quota_exhausted = True
            send_simple_message("âŒ Gemini API quota exhausted. No more article attempts this cycle.")
        else:
            send_simple_message(f"âŒ Error generating article: {error_str[:200]}")


def _generate_and_preview_image(article_title, source_url=None):
    """Generate a featured image and send it to Telegram for approval."""
    global _pending_image_path

    if not article_title:
        return

    send_simple_message("ðŸŽ¨ Generating featured image... This may take a moment.")

    try:
        webp_path, jpg_path = generate_featured_image(article_title, source_url=source_url)
        if webp_path and jpg_path:
            _pending_image_path = webp_path  # We use WebP for WordPress uploading
            save_pending_state()
            send_image_preview(jpg_path, article_title) # We use JPG for Telegram
            logger.info(f"ðŸ–¼ï¸ Image preview sent (Telegram: {jpg_path}, WP: {webp_path})")
        else:
            send_simple_message("âš ï¸ Image generation failed. Article can still be published without an image.")
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        send_simple_message(f"âš ï¸ Image generation failed: {str(e)[:200]}. Article can still be published without an image.")


def _handle_regenerate_image():
    """Regenerate the featured image for the pending article."""
    global _pending_image_path

    if not _pending_article and not load_pending_state():
        send_simple_message("âš ï¸ No article pending. Nothing to generate an image for.")
        return

    _pending_image_path = None
    _generate_and_preview_image(_pending_article.get("title", ""), _pending_article.get("source_url"))


def _handle_approve(status="draft", bypass_quality_gate=False):
    """Publish the pending article to WordPress."""
    global _pending_article, _pending_image_path, _publish_in_progress

    if not _pending_article and not load_pending_state():
        send_simple_message("âš ï¸ No article pending approval. Generate one first with âœï¸ Write Article.")
        return

    if _publish_in_progress:
        send_simple_message("Publish is already in progress. Please wait 10-20 seconds.")
        return

    _publish_in_progress = True
    logger.info(f"ðŸ“¤ Publishing article: {_pending_article['title']} (status: {status})")

    quality = validate_article_for_publish(_pending_article, min_words=getattr(config, "ARTICLE_MIN_WORDS", 700))
    if not quality["ok"] and not bypass_quality_gate:
        send_quality_gate_decision(_pending_article, quality, requested_status=status)
        logger.warning(f"Quality gate flagged article for manual decision: {quality}")
        _publish_in_progress = False
        return

    try:
        result = create_post(
            _pending_article,
            featured_image_path=_pending_image_path,
            status=status,
        )
        if result:
            img_note = " (with featured image)" if _pending_image_path else ""
            send_publish_confirmation(result["post_url"], _pending_article["title"], post_id=result["post_id"], status=status)
            logger.info(f"âœ… Published{img_note}: {result['post_url']}")
            try:
                from writer.seo_prompt import add_published_post
                add_published_post(
                    result["post_url"],
                    _pending_article["title"],
                    _pending_article.get("slug", ""),
                    published_at=datetime.utcnow().isoformat(),
                )
            except Exception:
                pass

            try:
                if _pending_article.get("scheme_id") and _pending_article.get("content_angle"):
                    conn_cov = get_connection()
                    mark_content_published(
                        conn_cov,
                        _pending_article.get("scheme_id", ""),
                        _pending_article.get("content_angle", ""),
                        _pending_article.get("title", ""),
                    )
                    conn_cov.close()
            except Exception as cov_err:
                logger.warning(f"Coverage publish tracking failed: {cov_err}")
            _pending_article = None
            _pending_image_path = None
            save_pending_state()
        else:
            from publisher import wordpress_client
            err = getattr(wordpress_client, "LAST_PUBLISH_ERROR", None)
            msg = "WordPress publishing failed."
            if err:
                msg += f" Reason: {err[:180]}"
            else:
                msg += " Check logs."
            if getattr(config, "WP_PUBLISH_WEBHOOK_URL", ""):
                msg += " Check webhook file and secret if configured."
            else:
                msg += " REST API may be blocked by firewall or bot protection."
            send_simple_message(f"âŒ {msg}")
    except Exception as e:
        logger.error(f"WordPress publish error: {e}")
        send_simple_message(f"âŒ Publishing error: {str(e)[:200]}")
    finally:
        _publish_in_progress = False

def _handle_publish_draft(post_id):
    """Publish an existing draft on WordPress."""
    from publisher.wordpress_client import update_post_status
    
    logger.info(f"ðŸš€ Publishing draft (ID: {post_id})")
    try:
        url = update_post_status(post_id, "publish")
        if url:
            send_simple_message(f"ðŸš€ Draft published successfully!\nðŸ”— {url}")
            logger.info(f"âœ… Draft {post_id} published: {url}")
        else:
            send_simple_message("âŒ Failed to publish draft. Check logs.")
    except Exception as e:
        logger.error(f"Draft publish error: {e}")
        send_simple_message(f"âŒ Error publishing draft: {str(e)[:200]}")


def run_agent_loop():
    """
    Main agent loop â€” runs scans at the configured interval.
    """
    interval = config.SCAN_INTERVAL_MINUTES

    logger.info("ðŸ¤– Women Empowerment Alerts Agent starting up...")
    logger.info(f"   Scan interval: {interval} minutes")
    logger.info(f"   Keywords tracked: {len(config.ALL_KEYWORDS)}")
    logger.info(f"   RSS feeds: {len(config.RSS_FEEDS)}")

    # Send startup notification
    send_status_update(
        f"Agent started at {datetime.now().strftime('%H:%M %Z')}\n"
        f"Monitoring {len(config.ALL_KEYWORDS)} keywords across {len(config.RSS_FEEDS)} RSS feeds + NewsAPI + Google Trends\n"
        f"Scan interval: every {interval} minutes"
    )

    scan_count = 0

    while True:
        try:
            scan_count += 1
            logger.info(f"\n{'=' * 60}")
            logger.info(f"SCAN #{scan_count}")
            logger.info(f"{'=' * 60}")

            alerts = run_scan()

            # Check for commands after each scan
            try:
                check_and_handle_commands()
            except Exception as e:
                logger.error(f"Command handler error: {e}")

            # Periodic cleanup
            if scan_count % 48 == 0:  # Every ~24 hours (at 30-min intervals)
                logger.info("ðŸ§¹ Running database cleanup...")
                conn = get_connection()
                cleanup_old_data(conn, days=7)
                conn.close()

            logger.info(f"ðŸ’¤ Next scan in {interval} minutes...")
            time.sleep(interval * 60)

        except KeyboardInterrupt:
            logger.info("\nâ¹ï¸ Agent stopped by user.")
            send_simple_message("â¹ï¸ Women Empowerment Agent has been stopped.")
            break
        except Exception as e:
            logger.error(f"âŒ Scan error: {e}", exc_info=True)
            logger.info(f"Retrying in {interval} minutes...")
            time.sleep(interval * 60)


def run_listen_loop():
    """
    Listen-only mode â€” polls for Telegram commands without running scans.
    Useful for handling /write_article, /approve etc. between scan cycles.
    """
    logger.info("ðŸ‘‚ Listening for Telegram commands...")
    send_simple_message("ðŸ‘‚ Agent is listening for commands. Tap âœï¸ Write Article on any alert.")

    while True:
        try:
            check_and_handle_commands()
            time.sleep(2)  # Poll every 2 seconds
        except KeyboardInterrupt:
            logger.info("\nâ¹ï¸ Listener stopped.")
            break
        except Exception as e:
            logger.error(f"Listen loop error: {e}")
            time.sleep(5)


def test_all_connections():
    """Test all API connections and report status."""
    # Ensure stdout can print emojis on Windows (avoid UnicodeEncodeError)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    print("ðŸ” Testing all connections...\n")

    # Telegram
    print("1ï¸âƒ£  Telegram Bot:")
    ok, name = test_connection()
    if ok:
        print(f"   âœ… Connected as @{name}")
        mid = send_simple_message("ðŸ§ª Connection test successful! Your Women Empowerment Agent is ready.")
        print(f"   âœ… Test message sent (ID: {mid})")
    else:
        print("   âŒ FAILED â€” Check TELEGRAM_BOT_TOKEN in .env")

    # NewsAPI
    print("\n2ï¸âƒ£  NewsAPI:")
    try:
        from newsapi import NewsApiClient
        newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
        result = newsapi.get_top_headlines(q="women welfare scheme", language="en", page_size=1)
        if result.get("status") == "ok":
            print(f"   âœ… Connected â€” {result.get('totalResults', 0)} results available")
        else:
            print(f"   âŒ FAILED â€” {result}")
    except Exception as e:
        print(f"   âŒ FAILED â€” {e}")

    # RSS Feeds
    print("\n3ï¸âƒ£  RSS Feeds:")
    import feedparser
    for name, url in list(config.RSS_FEEDS.items())[:3]:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                print(f"   âœ… {name}: {len(feed.entries)} entries")
            else:
                print(f"   âš ï¸ {name}: Feed parsed but empty")
        except Exception as e:
            print(f"   âŒ {name}: FAILED ({e})")

    # WordPress
    print("\n4ï¸âƒ£  WordPress (REST API):")
    from publisher.wordpress_client import test_wp_connection
    ok, wp_info = test_wp_connection()
    if ok:
        print(f"   âœ… Connected to {wp_info['url']} as {wp_info['user']}")
    else:
        print(f"   âŒ FAILED â€” {wp_info}")

    # Gemini
    print("\n5ï¸âƒ£  Gemini (Google Generative AI):")
    from gemini_client import test_gemini_connection
    ok, gem_info = test_gemini_connection()
    if ok:
        print(f"   âœ… Connected (Models available: {len(gem_info['models'])})")
    else:
        print(f"   âŒ FAILED â€” {gem_info}")

    # Database
    print("\n6ï¸âƒ£  Database (SQLite):")
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        print("   âœ… Local database connected")
    except Exception as e:
        print(f"   âŒ FAILED â€” {e}")

    print("\nâœ… Connection test complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Women Empowerment Alerts Agent â€” Indian women empowerment news & scheme blog")
    parser.add_argument("--once", action="store_true", help="Run a single scan and exit")
    parser.add_argument("--test", action="store_true", help="Test all API connections")
    parser.add_argument("--listen", action="store_true", help="Listen for Telegram commands only")
    args = parser.parse_args()

    if args.test:
        test_all_connections()
    elif args.listen:
        run_listen_loop()
    elif args.once:
        logger.info("Running single scan and processing commands...")

        # 0. Load state including telegram offset
        load_pending_state()

        # 1. Poll for pending callbacks FIRST (catches clicks from previous 45-min window)
        logger.info("Checking for pending Telegram commands from previous runs...")
        for _ in range(12):  # 2 min of checks before scan
            try:
                check_and_handle_commands()
            except Exception as e:
                logger.error(f"Command handler error: {e}")
            time.sleep(10)

        # 2. Run the scan
        alerts = run_scan()

        # 3. Poll for callbacks after scan â€” longer window so you can review & click
        #    (alerts>0: 6 min | alerts=0: 2 min â€” covers approve/reject on previous article)
        poll_seconds = 360 if alerts > 0 else 120
        logger.info(f"Polling for commands for {poll_seconds//60} minutes...")
        end_time = time.time() + poll_seconds
        while time.time() < end_time:
            try:
                check_and_handle_commands()
            except Exception as e:
                logger.error(f"Command handler error after scan: {e}")
            time.sleep(5)

        # 4. Persist state for next run (critical for GitHub Actions cache)
        save_pending_state()
        try:
            with open("latest_topics.json", "w", encoding="utf-8") as f:
                json.dump(_latest_topics, f, default=str)
        except Exception as e:
            logger.error(f"Failed to save latest topics: {e}")

        # 5. Acknowledge processed updates
        if _update_offset:
            try:
                get_updates(offset=_update_offset)
                logger.info(f"Acknowledged Telegram updates up to offset {_update_offset}")
            except Exception as e:
                logger.error(f"Failed to clear final updates: {e}")

        logger.info("Done.")
    else:
        run_agent_loop()






