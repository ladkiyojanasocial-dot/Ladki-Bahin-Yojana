"""
Quality gate checks before publishing articles.
"""
import re
import config


def _normalize_text(value):
    value = (value or "").lower()
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[^a-z0-9\u0900-\u097f\u0c00-\u0c7f\s]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def validate_article_for_publish(article, min_words=700):
    issues = []
    warnings = []

    article = article or {}
    title = article.get("title", "").strip()
    meta = article.get("meta_description", "").strip()
    full_content = article.get("full_content") or article.get("content_html") or ""
    content_text = re.sub(r"<[^>]+>", " ", full_content)
    words = [w for w in content_text.split() if w.strip()]
    intro_text = " ".join(words[:120])
    focus_keyword = (article.get("matched_keyword") or article.get("title") or "").strip()

    normalized_keyword = _normalize_text(focus_keyword)
    normalized_title = _normalize_text(title)
    normalized_meta = _normalize_text(meta)
    normalized_intro = _normalize_text(intro_text)

    if len(title) < 35:
        warnings.append("Title is short; improve clarity for search CTR")
    if len(title) > 65:
        issues.append("Title is too long (recommended <= 65 characters)")

    if len(meta) < 120:
        warnings.append("Meta description is short; target 120-155 characters")
    if len(meta) > 165:
        issues.append("Meta description is too long (recommended <= 165 characters)")

    if len(words) < min_words:
        issues.append(f"Article is thin ({len(words)} words); needs at least {min_words} words")

    base_url = re.escape(config.WP_URL.rstrip("/"))
    internal_links = len(re.findall(rf'<a\s+[^>]*href="{base_url}/', full_content, flags=re.IGNORECASE))
    if internal_links < 2:
        issues.append("Internal linking is weak (needs at least 2 internal links)")

    h2_count = len(re.findall(r"<h2\b", full_content, flags=re.IGNORECASE))
    if h2_count < 2:
        issues.append("Content structure is weak (needs at least 2 H2 sections)")

    bullet_count = len(re.findall(r"<(ul|ol)\b", full_content, flags=re.IGNORECASE))
    if bullet_count < 2:
        warnings.append("Scannable structure is weak; add more bullet or step lists")

    if len(intro_text) < 260:
        warnings.append("Intro is weak; add a clearer hook and early answer")

    if normalized_keyword and len(normalized_keyword) >= 4:
        if normalized_keyword not in normalized_title:
            issues.append("Focus keyword is missing from title")
        if normalized_keyword not in normalized_meta:
            warnings.append("Focus keyword is missing from meta description")
        if normalized_keyword not in normalized_intro:
            issues.append("Focus keyword is missing from the first 120 words")

    if "FAQPage" not in full_content:
        warnings.append("FAQ schema missing; rich result chance reduced")

    if not re.search(r"frequently asked questions|faq", content_text, flags=re.IGNORECASE):
        warnings.append("FAQ section heading is missing")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "word_count": len(words),
        "internal_links": internal_links,
        "h2_count": h2_count,
        "focus_keyword": focus_keyword,
    }
