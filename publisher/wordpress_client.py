"""
WordPress Client - Handles all WordPress REST API interactions:
creating posts, uploading media, setting categories/tags,
and injecting RankMath SEO fields.
"""
import base64
import json
import logging
import os
import re
import time
from html import unescape

import requests
from requests.auth import HTTPBasicAuth

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)

LAST_PUBLISH_ERROR = None

API_BASE = f"{config.WP_URL}/wp-json/wp/v2"
AUTH = HTTPBasicAuth(config.WP_USERNAME, config.WP_APP_PASSWORD)
TIMEOUT = 30
RETRY_DELAY = 5
RETRY_403_DELAY = 4
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LadkiBahinAgent/1.0; +https://womenempowermentportal.org)",
    "Referer": f"{config.WP_URL}/",
    "Accept": "application/json, */*; q=0.1",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": config.WP_URL.rstrip("/"),
}


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return None


def _coerce_int(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _extract_id_from_location(response):
    if response is None:
        return None
    location = response.headers.get("Location") or response.headers.get("Content-Location") or ""
    match = re.search(r"/(\d+)(?:/)?$", location)
    if match:
        return int(match.group(1))
    return None


def _extract_wp_entity_id(payload, response=None):
    """
    Extract a numeric WordPress entity ID from standard and mildly non-standard payloads.
    """
    if isinstance(payload, dict):
        for key in ("id", "ID", "post_id", "media_id"):
            entity_id = _coerce_int(payload.get(key))
            if entity_id:
                return entity_id

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("id", "ID", "post_id", "media_id"):
                entity_id = _coerce_int(data.get(key))
                if entity_id:
                    return entity_id

    return _extract_id_from_location(response)


def _resolve_post_id_from_slug(slug):
    if not slug:
        return None
    try:
        response = requests.get(
            f"{API_BASE}/posts",
            params={"slug": slug, "context": "edit", "per_page": 1},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            posts = _safe_json(response) or []
            if posts:
                return _extract_wp_entity_id(posts[0], response)
    except Exception as e:
        logger.warning(f"  Could not resolve post by slug '{slug}': {e}")
    return None


def _get_rankmath_payload(article):
    focus_kw = article.get("matched_keyword", "") or article.get("focus_keyword", "")
    if not focus_kw and article.get("tags"):
        focus_kw = article["tags"][0]
    if not focus_kw:
        focus_kw = article.get("title", "")

    seo_title = (article.get("seo_title") or article.get("title") or "Untitled").strip()
    meta_description = (article.get("meta_description") or "").strip()

    return {
        "rank_math_title": seo_title,
        "rank_math_description": meta_description,
        "rank_math_focus_keyword": focus_kw,
    }


SITE_KEYWORD_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "site_keyword_inventory.json")
SITE_KEYWORD_CACHE_TTL_SECONDS = 6 * 60 * 60


def _normalize_keywordish(value):
    value = unescape(str(value or "")).lower()
    value = re.sub(r'<[^>]+>', ' ', value)
    value = re.sub(r'[^a-z0-9]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def _build_local_inventory():
    inventory = {"keywords": set(), "titles": set(), "slugs": set(), "posts": []}
    posts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "published_posts.json")
    if not os.path.exists(posts_file):
        return inventory
    try:
        with open(posts_file, "r", encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return inventory

    for row in rows:
        title = _normalize_keywordish(row.get("title", ""))
        slug = _normalize_keywordish((row.get("slug", "") or "").replace("-", " "))
        focus_keyword = _normalize_keywordish(row.get("focus_keyword", ""))
        if title:
            inventory["titles"].add(title)
        if slug:
            inventory["slugs"].add(slug)
        if focus_keyword:
            inventory["keywords"].add(focus_keyword)
        inventory["posts"].append({
            "title": row.get("title", ""),
            "slug": row.get("slug", ""),
            "focus_keyword": row.get("focus_keyword", ""),
            "url": row.get("url", ""),
        })
    return inventory


def _read_site_keyword_cache():
    if not os.path.exists(SITE_KEYWORD_CACHE_FILE):
        return None
    try:
        with open(SITE_KEYWORD_CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        fetched_at = float(payload.get("fetched_at", 0))
        if fetched_at and (time.time() - fetched_at) <= SITE_KEYWORD_CACHE_TTL_SECONDS:
            return payload.get("inventory")
    except Exception:
        return None
    return None


def _write_site_keyword_cache(inventory):
    serializable = {
        "keywords": sorted(inventory.get("keywords", set())),
        "titles": sorted(inventory.get("titles", set())),
        "slugs": sorted(inventory.get("slugs", set())),
        "posts": inventory.get("posts", []),
    }
    try:
        with open(SITE_KEYWORD_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"fetched_at": time.time(), "inventory": serializable}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return serializable


def get_site_keyword_inventory(force_refresh=False):
    if not force_refresh:
        cached = _read_site_keyword_cache()
        if cached:
            return cached

    inventory = _build_local_inventory()
    if not config.WP_URL or not config.WP_USERNAME or not config.WP_APP_PASSWORD:
        return _write_site_keyword_cache(inventory)

    page = 1
    while page <= 20:
        try:
            response = requests.get(
                f"{API_BASE}/posts",
                params={
                    "status": "publish",
                    "context": "edit",
                    "per_page": 100,
                    "page": page,
                    "_fields": "id,slug,title,link,meta",
                },
                auth=AUTH,
                headers=HEADERS,
                timeout=TIMEOUT,
            )
        except Exception as e:
            logger.warning(f"  Could not refresh published keyword inventory from WordPress: {e}")
            break

        if response.status_code != 200:
            logger.warning(f"  WordPress keyword inventory fetch returned HTTP {response.status_code}")
            break

        posts = _safe_json(response) or []
        if not posts:
            break

        for post in posts:
            meta = post.get("meta") if isinstance(post.get("meta"), dict) else {}
            title_text = _normalize_keywordish((post.get("title") or {}).get("rendered", ""))
            slug_text = _normalize_keywordish((post.get("slug") or "").replace("-", " "))
            focus_keyword = _normalize_keywordish(meta.get("rank_math_focus_keyword", ""))
            if title_text:
                inventory["titles"].add(title_text)
            if slug_text:
                inventory["slugs"].add(slug_text)
            if focus_keyword:
                inventory["keywords"].add(focus_keyword)
            inventory["posts"].append({
                "id": post.get("id"),
                "title": (post.get("title") or {}).get("rendered", ""),
                "slug": post.get("slug", ""),
                "focus_keyword": meta.get("rank_math_focus_keyword", ""),
                "url": post.get("link", ""),
            })

        if len(posts) < 100:
            break
        page += 1

    return _write_site_keyword_cache(inventory)


def find_published_topic_match(topic_title="", matched_keyword="", slug=""):
    inventory = get_site_keyword_inventory()
    normalized_keyword = _normalize_keywordish(matched_keyword)
    normalized_title = _normalize_keywordish(topic_title)
    normalized_slug = _normalize_keywordish((slug or "").replace("-", " "))

    if normalized_keyword and normalized_keyword in set(inventory.get("keywords", [])):
        return {"reason": "focus keyword", "value": matched_keyword.strip()}
    if normalized_title and normalized_title in set(inventory.get("titles", [])):
        return {"reason": "title", "value": topic_title.strip()}
    if normalized_slug and normalized_slug in set(inventory.get("slugs", [])):
        return {"reason": "slug", "value": slug.strip()}
    return None


def topic_already_published(topic_title="", matched_keyword="", slug=""):
    return find_published_topic_match(topic_title=topic_title, matched_keyword=matched_keyword, slug=slug) is not None


def create_post(article, featured_image_path=None, status=None):
    """
    Create a WordPress post from an article dict.
    If WP_PUBLISH_WEBHOOK_URL and WP_PUBLISH_SECRET are set, publishes via webhook.
    Otherwise uses the REST API with retries for transient firewall or upstream failures.
    """
    if status is None:
        status = config.WP_DEFAULT_STATUS

    global LAST_PUBLISH_ERROR
    LAST_PUBLISH_ERROR = None

    if getattr(config, "WP_PUBLISH_WEBHOOK_URL", None) and getattr(config, "WP_PUBLISH_SECRET", None):
        logger.info(f"Publishing to WordPress via webhook: '{article.get('title', 'Untitled')}'")
        out = _publish_via_webhook(article, featured_image_path, status)
        if out is None and LAST_PUBLISH_ERROR:
            logger.error(f"  Webhook: {LAST_PUBLISH_ERROR}")
        return out

    logger.info(f"Publishing to WordPress: '{article.get('title', 'Untitled')}'")

    media_id = None
    if featured_image_path and os.path.exists(featured_image_path):
        media_id = upload_media(featured_image_path, article.get("title", ""))

    category_id = get_or_create_category(article.get("category", config.WP_DEFAULT_CATEGORY))

    tag_ids = []
    for tag_name in article.get("tags", []):
        tag_id = get_or_create_tag(tag_name)
        if tag_id:
            tag_ids.append(tag_id)

    rankmath_meta = _get_rankmath_payload(article)

    post_data = {
        "title": article.get("title", "Untitled"),
        "content": article.get("full_content", article.get("content", "")),
        "excerpt": article.get("meta_description", ""),
        "slug": article.get("slug", ""),
        "status": status,
        "categories": [category_id] if category_id else [],
        "tags": tag_ids,
        "comment_status": "open",
    }

    if media_id:
        post_data["featured_media"] = media_id

    article_lang = article.get("lang", "")
    post_data.setdefault("meta", {})
    post_data["meta"].update(rankmath_meta)
    if article_lang:
        post_data["meta"]["_kisan_lang"] = article_lang
        logger.info(f"  Language tag: {article_lang}")

    try:
        response = None
        for attempt in range(3):
            response = requests.post(
                f"{API_BASE}/posts",
                json=post_data,
                auth=AUTH,
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            if response.status_code in (200, 201):
                result = _safe_json(response) or {}
                post_id = _extract_wp_entity_id(result, response)
                if not post_id:
                    post_id = _resolve_post_id_from_slug(article.get("slug", ""))
                post_url = result.get("link", "")
                if not post_url and post_id:
                    post_url = f"{config.WP_URL.rstrip('/')}/?p={post_id}"

                if not post_id:
                    body_preview = response.text[:500] if response.text else "empty response body"
                    logger.error("  Post creation response did not include a usable post ID.")
                    logger.error(f"     Response: {body_preview}")
                    LAST_PUBLISH_ERROR = "Post created but ID missing in response"
                    return None

                logger.info(f"  Post created (ID: {post_id}, Status: {status})")
                logger.info(f"  URL: {post_url}")

                _set_rankmath_meta(post_id, article)

                if status in ["publish", "publish_live", "future"]:
                    try:
                        from writer.seo_prompt import add_published_post
                        from datetime import datetime
                        add_published_post(
                            post_url,
                            article.get("title", ""),
                            article.get("slug", ""),
                            published_at=datetime.utcnow().isoformat(),
                            focus_keyword="",
                        )
                    except Exception as e:
                        logger.warning(f"  Could not add published post for internal links: {e}")

                return {
                    "post_id": post_id,
                    "post_url": post_url,
                    "status": status,
                }
            if response.status_code in (502, 503) and attempt < 2:
                logger.warning(f"  WordPress returned {response.status_code}, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            if response.status_code == 403 and attempt < 2:
                logger.warning(f"  WordPress returned 403, retrying in {RETRY_403_DELAY}s (attempt {attempt + 1}/3)...")
                time.sleep(RETRY_403_DELAY)
                continue
            if "json" not in (response.headers.get("content-type") or "").lower() and attempt < 2:
                logger.warning(f"  WordPress returned non-JSON content, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            break

        status_code = response.status_code if response is not None else "unknown"
        body_preview = response.text[:500] if response is not None else "no response body"
        logger.error(f"  Post creation failed: HTTP {status_code}")
        logger.error(f"     Response: {body_preview}")
        LAST_PUBLISH_ERROR = f"REST HTTP {status_code}"
        if response is not None and "json" not in (response.headers.get("content-type") or "").lower():
            LAST_PUBLISH_ERROR += " (non-JSON/WAF block)"
        if response is not None and response.status_code == 403:
            logger.error("     Tip: 403 often means firewall or bot protection blocking the REST API.")
        return None

    except Exception as e:
        logger.error(f"  Post creation error: {e}")
        LAST_PUBLISH_ERROR = str(e)[:150]
        return None


def _publish_via_webhook(article, featured_image_path=None, status=None):
    """
    Publish via webhook on the user's server. No REST API from the agent means no firewall block.
    Requires the publish webhook to be deployed on the server and WP_PUBLISH_WEBHOOK_URL +
    WP_PUBLISH_SECRET in env.
    """
    global LAST_PUBLISH_ERROR
    url = config.WP_PUBLISH_WEBHOOK_URL
    secret = config.WP_PUBLISH_SECRET
    if not url or not secret:
        return None

    rankmath_meta = _get_rankmath_payload(article)
    payload = {
        "title": article.get("title", "Untitled"),
        "content": article.get("full_content", article.get("content", "")),
        "excerpt": article.get("meta_description", ""),
        "slug": article.get("slug", ""),
        "status": status or config.WP_DEFAULT_STATUS,
        "tags": article.get("tags", []),
        "category": article.get("category", config.WP_DEFAULT_CATEGORY),
        "rank_math_title": rankmath_meta["rank_math_title"],
        "rank_math_description": rankmath_meta["rank_math_description"],
        "rank_math_focus_keyword": rankmath_meta["rank_math_focus_keyword"],
        "faq_schema": article.get("faq_schema", ""),
        "lang": article.get("lang", ""),
    }
    if featured_image_path and os.path.exists(featured_image_path):
        with open(featured_image_path, "rb") as f:
            payload["featured_image_base64"] = base64.b64encode(f.read()).decode("ascii")
        payload["featured_image_filename"] = os.path.basename(featured_image_path)
        payload["featured_image_alt"] = article.get("title", "")

    for attempt in range(3):
        headers = HEADERS.copy()
        headers.update({
            "Content-Type": "application/json",
            "X-Kisan-Agent-Token": secret,
        })
        headers.pop("Accept-Encoding", None)

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                data = _safe_json(response)
                if data and data.get("success"):
                    logger.info(f"  Post created via webhook (ID: {data.get('post_id')}, URL: {data.get('post_url', '')})")
                    seo_meta = data.get("seo_meta") or {}
                    if seo_meta:
                        logger.info(
                            "  RankMath meta stored via webhook "
                            f"(title={bool(seo_meta.get('rank_math_title'))}, "
                            f"description={bool(seo_meta.get('rank_math_description'))}, "
                            f"focus={bool(seo_meta.get('rank_math_focus_keyword'))})"
                        )
                    if data.get("assigned_category_id") or data.get("assigned_tag_ids"):
                        logger.info(
                            f"  Webhook taxonomy assignment: category={data.get('assigned_category_id')} "
                            f"tags={data.get('assigned_tag_ids', [])}"
                        )
                    if data.get("post_id"):
                        try:
                            _set_rankmath_meta(data.get("post_id"), article)
                        except Exception as e:
                            logger.debug(f"  RankMath REST sync after webhook failed: {e}")
                    return {
                        "post_id": data.get("post_id"),
                        "post_url": data.get("post_url", ""),
                        "status": data.get("status", status),
                    }
                if data:
                    logger.error(f"  Webhook returned success=false: {data.get('message', '')}")
                    LAST_PUBLISH_ERROR = data.get("message", "success=false")
                else:
                    logger.error(f"  Webhook returned non-JSON success response: {response.text[:200]}")
                    LAST_PUBLISH_ERROR = "Webhook returned non-JSON response"
                return None
            if response.status_code in (502, 503, 403) and attempt < 2:
                logger.warning(f"  Webhook returned {response.status_code}, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            err = f"HTTP {response.status_code}"
            if response.text:
                preview = response.text.strip()
                err += " - " + (preview[:150] + "..." if len(preview) > 150 else preview)
            logger.error(f"  Webhook failed: {err}")
            LAST_PUBLISH_ERROR = err
            return None
        except Exception as e:
            logger.warning(f"  Webhook request error (attempt {attempt + 1}/3): {e}")
            LAST_PUBLISH_ERROR = str(e)[:150]
            if attempt < 2:
                time.sleep(RETRY_DELAY)
    return None


def upload_media(file_path, title=""):
    """
    Upload an image file to WordPress media library.

    Returns:
        int: media ID, or None if failed
    """
    filename = os.path.basename(file_path)
    mime_type = _get_mime_type(filename)

    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        headers = HEADERS.copy()
        headers.update({
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": mime_type,
        })

        response = None
        for attempt in range(3):
            response = requests.post(
                f"{API_BASE}/media",
                data=file_data,
                headers=headers,
                auth=AUTH,
                timeout=60,
            )
            if response.status_code in (200, 201):
                payload = _safe_json(response) or {}
                media_id = _extract_wp_entity_id(payload, response)
                if not media_id:
                    body_preview = response.text[:300] if response.text else "empty response body"
                    logger.error("  Media upload response did not include a usable media ID.")
                    logger.error(f"     Response: {body_preview}")
                    return None

                logger.info(f"  Image uploaded (Media ID: {media_id})")

                if title:
                    requests.post(
                        f"{API_BASE}/media/{media_id}",
                        json={"alt_text": title[:125]},
                        auth=AUTH,
                        headers=HEADERS,
                        timeout=15,
                    )
                return media_id
            if response.status_code in (502, 503) and attempt < 2:
                logger.warning(f"  Media upload returned {response.status_code}, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            if response.status_code == 403 and attempt < 2:
                logger.warning(f"  Media upload returned 403, retrying in {RETRY_403_DELAY}s (attempt {attempt + 1}/3)...")
                time.sleep(RETRY_403_DELAY)
                continue
            break

        status_code = response.status_code if response is not None else "unknown"
        body_preview = response.text[:300] if response is not None else "no response body"
        logger.error(f"  Media upload failed: HTTP {status_code}")
        logger.error(f"     {body_preview}")
        return None

    except Exception as e:
        logger.error(f"  Media upload error: {e}")
        return None


def get_or_create_category(name):
    """Get category ID by name, creating it if it doesn't exist."""
    name = re.sub(r'[*_#`]', '', name).strip()

    try:
        response = requests.get(
            f"{API_BASE}/categories",
            params={"slug": name, "per_page": 1},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code == 200:
            categories = _safe_json(response) or []
            if categories:
                return categories[0]["id"]

        response = requests.get(
            f"{API_BASE}/categories",
            params={"search": name, "per_page": 5},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code == 200:
            categories = _safe_json(response) or []
            for cat in categories:
                if cat["name"].lower() == name.lower() or cat["slug"].lower() == name.lower():
                    return cat["id"]

        create_name = "News" if name.lower() == "news" else name
        response = requests.post(
            f"{API_BASE}/categories",
            json={"name": create_name, "slug": name},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code in (200, 201):
            cat_id = (_safe_json(response) or {}).get("id")
            logger.info(f"  Created category '{create_name}' (ID: {cat_id})")
            return cat_id

    except Exception as e:
        logger.error(f"  Category error for '{name}': {e}")

    if name != "News":
        return get_or_create_category("News")
    return None


def get_or_create_tag(name):
    """Get tag ID by name, creating it if it doesn't exist."""
    try:
        response = requests.get(
            f"{API_BASE}/tags",
            params={"search": name, "per_page": 5},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code == 200:
            tags = _safe_json(response) or []
            for tag in tags:
                if tag["name"].lower() == name.lower():
                    return tag["id"]

        response = requests.post(
            f"{API_BASE}/tags",
            json={"name": name},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code in (200, 201):
            return (_safe_json(response) or {}).get("id")

    except Exception as e:
        logger.error(f"  Tag error for '{name}': {e}")

    return None


def _set_rankmath_meta(post_id, article):
    """
    Set RankMath SEO metadata on a post.
    Uses PATCH so only meta is updated. Meta keys must be registered in WP.
    """
    if not _coerce_int(post_id):
        logger.warning("  Skipping RankMath update because post_id is missing.")
        return

    meta_values = _get_rankmath_payload(article)
    focus_kw = meta_values["rank_math_focus_keyword"]

    rankmath_meta = {
        "meta": {
            **meta_values,
            "rank_math_robots": ["index", "follow"],
        }
    }

    faq_schema = article.get("faq_schema", "")
    if faq_schema:
        clean_schema = re.sub(r'<script.*?>|</script>', '', faq_schema, flags=re.IGNORECASE | re.DOTALL).strip()
        rankmath_meta["meta"]["_ssi_schema_faq"] = clean_schema

    try:
        response = requests.request(
            "PATCH",
            f"{API_BASE}/posts/{post_id}",
            json=rankmath_meta,
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code == 200:
            logger.info(f"  RankMath SEO metadata set (focus: '{focus_kw}')")
        else:
            body_preview = response.text[:300] if response.text else "empty response body"
            logger.warning(
                f"  RankMath meta update returned HTTP {response.status_code}. "
                "Add deploy/rankmath-rest-snippet.php to your theme's functions.php so meta is writable via REST."
            )
            logger.warning(f"     Response: {body_preview}")
    except Exception as e:
        logger.warning(f"  RankMath meta update failed: {e}")


def update_post_status(post_id, status="publish"):
    """Update a post's status (e.g., from draft to publish). Uses webhook if configured, else REST API."""
    if getattr(config, "WP_PUBLISH_WEBHOOK_URL", None) and getattr(config, "WP_PUBLISH_SECRET", None):
        return _update_status_via_webhook(post_id, status)
    try:
        response = requests.post(
            f"{API_BASE}/posts/{post_id}",
            json={"status": status},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            post_data = _safe_json(response) or {}
            link = post_data.get("link")

            if status == "publish":
                try:
                    from writer.seo_prompt import add_published_post
                    from datetime import datetime
                    title = post_data.get("title", {}).get("rendered", "")
                    slug = post_data.get("slug", "")
                    if link and title:
                        add_published_post(
                            link,
                            title,
                            slug,
                            published_at=datetime.utcnow().isoformat(),
                            focus_keyword=article.get("matched_keyword", "") or article.get("focus_keyword", ""),
                        )
                except Exception as e:
                    logger.warning(f"  Could not add published post for internal links from draft update: {e}")

            return link
        logger.error(f"Failed to update post status: HTTP {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error updating post status: {e}")
        return None


def _update_status_via_webhook(post_id, status="publish"):
    """Update post status via webhook using the same endpoint as create."""
    url = config.WP_PUBLISH_WEBHOOK_URL
    secret = config.WP_PUBLISH_SECRET
    if not url or not secret:
        return None

    try:
        headers = HEADERS.copy()
        headers.update({
            "Content-Type": "application/json",
            "X-Kisan-Agent-Token": secret,
        })
        headers.pop("Accept-Encoding", None)

        response = requests.post(
            url,
            json={"action": "publish_draft", "post_id": int(post_id), "status": status},
            headers=headers,
            timeout=30,
        )
        if response.status_code == 200:
            data = _safe_json(response)
            if data and data.get("success"):
                return data.get("post_url")
            if not data:
                logger.error(f"Publish draft webhook: response not JSON: {response.text[:200]}")
                return None
        logger.warning(f"Publish draft webhook: HTTP {response.status_code} - {response.text[:300]}")
        return None
    except Exception as e:
        logger.warning(f"Webhook status update failed: {e}")
        return None


def _get_mime_type(filename):
    """Determine MIME type from filename."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return mime_map.get(ext, "image/jpeg")


def test_wordpress_connection():
    """Test the WordPress REST API connection."""
    try:
        response = requests.get(
            f"{API_BASE}/posts",
            params={"per_page": 1},
            auth=AUTH,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code == 200:
            posts = _safe_json(response) or []
            logger.info(
                f"WordPress: Connected. Latest post: '{posts[0]['title']['rendered'][:50]}'"
                if posts else "WordPress: Connected. No posts found."
            )
            return True

        logger.error(f"WordPress: HTTP {response.status_code}")
        return False

    except Exception as e:
        logger.error(f"WordPress connection failed: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    if test_wordpress_connection():
        print("WordPress connection successful!")
    else:
        print("WordPress connection failed!")




