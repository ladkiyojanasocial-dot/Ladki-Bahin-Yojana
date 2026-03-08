"""
Article Generator â€” Uses Gemini to write SEO-optimized articles
from source material gathered by the source fetcher.
"""
import logging
import re
import time

from google import genai

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from writer.source_fetcher import fetch_multiple_sources
from writer.seo_prompt import build_article_prompt, get_category_for_topic, get_outbound_links_for_prompt
from detection.language_router import normalize_lang
from gemini_client import generate_content_with_fallback

logger = logging.getLogger(__name__)

# Gemini retry handled by gemini_client


def _search_news_for_trend(keyword):
    """Search Google News RSS and NewsAPI to find background context for a trending keyword."""
    urls = []
    
    # 1. Google News RSS
    try:
        import feedparser
        import urllib.parse
        encoded_kw = urllib.parse.quote(keyword)
        rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:3]:
            if entry.link and entry.link not in urls:
                urls.append(entry.link)
    except Exception as e:
        logger.warning(f"Failed to fetch Google News RSS for trend: {e}")

    # 2. NewsAPI
    try:
        from newsapi import NewsApiClient
        from datetime import datetime, timedelta
        newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
        from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
        results = newsapi.get_everything(
            q=keyword,
            language="en",
            sort_by="relevancy",
            from_param=from_date,
            page_size=5
        )
        if results.get("status") == "ok":
            for article in results.get("articles", [])[:3]:
                url = article.get("url")
                if url and url not in urls:
                    urls.append(url)
    except Exception as e:
        logger.warning(f"Failed to fetch NewsAPI for trend: {e}")
        
    return urls


def _ensure_article_taxonomy(article, topic):
    keyword = (article.get("matched_keyword") or topic.get("matched_keyword") or "Women Welfare").strip()
    default_tags = [
        keyword,
        (topic.get("content_angle") or "Women Scheme Guide").replace("_", " ").title(),
        "Women Welfare",
        "Government Scheme",
        "Latest Update",
    ]
    seen = set()
    final_tags = []
    for tag in list(article.get("tags", [])) + default_tags:
        clean = re.sub(r"\s+", " ", str(tag or "")).strip(" ,.-")
        if not clean:
            continue
        lowered = clean.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        final_tags.append(clean[:40])
        if len(final_tags) == 5:
            break
    while len(final_tags) < 5:
        filler = f"Women Update {len(final_tags) + 1}"
        if filler.lower() in seen:
            continue
        final_tags.append(filler)
        seen.add(filler.lower())
    article["tags"] = final_tags
    if not article.get("category") or article.get("category") == "uncategorized":
        article["category"] = get_category_for_topic(topic.get("topic", ""), keyword)
    return article


def _ensure_outbound_source_link(article, source_texts):
    full_content = article.get("full_content") or article.get("content_html") or ""
    if re.search(r'<a\s+[^>]*href="https?://', full_content, flags=re.IGNORECASE):
        return article

    outbound_links = get_outbound_links_for_prompt(source_texts, topic.get("topic", ""), topic.get("matched_keyword", ""))
    if not outbound_links:
        return article

    chosen = outbound_links[0]
    anchor_text = chosen.get("label") or "official source"
    link_html = (
        '\n<p><strong>Official source:</strong> '
        f'<a href="{chosen["url"]}">{anchor_text}</a></p>\n'
    )

    if article.get("content_html"):
        article["content_html"] = article["content_html"].rstrip() + link_html
    if article.get("full_content"):
        if "</div>" in article["full_content"]:
            article["full_content"] = article["full_content"].replace("</div>", link_html + "</div>", 1)
        else:
            article["full_content"] = article["full_content"].rstrip() + link_html
    if article.get("content"):
        article["content"] = article["content"].rstrip() + f"\n\nOfficial source: {chosen['url']}"
    return article


def generate_article(topic, source_urls=None):
    """
    Generate a complete SEO-optimized article for a trending topic.
    """
    logger.info(f"ðŸ“ Generating article for: {topic.get('topic', 'Unknown')}")

    # â”€â”€ Step 1: Gather source material â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if source_urls is None:
        source_urls = []
        for story in topic.get("stories", []):
            url = story.get("url", "")
            if url and url.startswith("http"):
                source_urls.append(url)

    # Also add the top_url if available
    top_url = topic.get("top_url", "")
    if top_url and top_url not in source_urls:
        source_urls.insert(0, top_url)

    # Check if this is a pure trend alert
    is_pure_trend = True
    if not source_urls:
        is_pure_trend = True
    else:
        for url in source_urls:
            if "trends.google.com" not in url:
                is_pure_trend = False
                break
                
    if is_pure_trend:
        keyword = topic.get("matched_keyword") or topic.get("topic", "").replace("Rising search:", "").strip()
        logger.info(f"  ðŸ” Pure trend detected. Searching active news for: '{keyword}'")
        found_urls = _search_news_for_trend(keyword)
        if found_urls:
            source_urls.extend(found_urls)
            logger.info(f"  âœ… Found {len(found_urls)} background articles for context.")

    logger.info(f"  Fetching {len(source_urls)} source URLs...")
    source_texts = fetch_multiple_sources(source_urls, max_sources=8)

    if not source_texts:
        logger.warning("  âš ï¸ No source material could be extracted. Using topic summary only.")
        source_texts = [{
            "title": topic.get("topic", ""),
            "text": "\n".join(s.get("summary", "") for s in topic.get("stories", [])),
            "source_domain": "aggregated_summaries",
            "url": "",
        }]

    # â”€â”€ Step 2: Build the prompt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    target_lang = normalize_lang(topic.get("lang", "en"))

    try:
        prompt = build_article_prompt(
            topic_title=topic.get("topic", "Women Welfare News Update"),
            source_texts=source_texts,
            matched_keyword=topic.get("matched_keyword", ""),
            target_lang=target_lang,
            content_angle=topic.get("content_angle", ""),
        )
    except Exception as e:
        logger.error(f"  âŒ Failed to build prompt: {e}")
        return None

    # â”€â”€ Step 3: Call Gemini â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        logger.info("  ðŸ¤– Calling Gemini API...")
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents=prompt
        )
        raw_output = (getattr(response, "text", None) or "").strip()
        if not raw_output:
            logger.error("  âŒ Gemini returned empty or blocked content (no text). Try again or check API/safety settings.")
            return None
        logger.info(f"  âœ… Gemini responded ({len(raw_output)} chars)")
        logger.debug(f"RAW AI OUTPUT:\n{raw_output}")

    except Exception as e:
        logger.error(f"  âŒ Gemini API error: {e}")
        return None

    # â”€â”€ Step 4: Parse structured output â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    article = _parse_article_output(
        raw_output,
        matched_keyword=topic.get("matched_keyword", ""),
        topic_title=topic.get("topic", ""),
    )

    if article:
        # Ensure we have usable content (model sometimes omits markers)
        if len(article.get("content", "") or "") < 100:
            logger.warning("  âš ï¸ Parsed content too short; treating as parse failure.")
            logger.debug(f"  Raw output preview: {raw_output[:500]}...")
            return None
        article["sources_used"] = [s.get("source_domain", "") for s in source_texts]
        article = _ensure_article_taxonomy(article, topic)
        article["lang"] = target_lang if target_lang in ("en", "hi", "te") else article.get("lang", "en")
        article = _ensure_outbound_source_link(article, source_texts)
        article["word_count"] = len((article.get("content_html") or article.get("full_content") or "").split())
        logger.info(f"  Article generated: '{article['title']}' (category: {article['category']})")
    else:
        logger.error("  âŒ Failed to parse Gemini output. Check that the model returns TITLE, CONTENT_START/END, etc.")
        logger.debug(f"  Raw output preview: {raw_output[:400]}...")

    return article


def _parse_article_output(raw_text, matched_keyword="", topic_title=""):
    """
    Parse the structured output from Gemini into article components.
    Includes robust fallback logic for when AI omits labels or markers.
    """
    try:
        result = {}
        
        # Helper to strip markdown and excessive punctuation
        def clean_meta(val):
            if not val: return ""
            # Strip markdown artifacts and quotes
            return re.sub(r'[*_#`"]', '', val).strip()

        # â”€â”€ 1. TITLE â”€â”€ (enforce max 60 chars for SEO)
        MAX_TITLE_LEN = 60
        title_match = re.search(r'(?:1\.|TITLE:)\s*(.+?)(?:\n|2\.|SEO_TITLE:|3\.|META_DESCRIPTION:|---|$)', raw_text, re.IGNORECASE | re.DOTALL)
        if title_match:
            result["title"] = clean_meta(title_match.group(1))
        else:
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            result["title"] = clean_meta(lines[0]) if lines else "Women Welfare Update"
        if len(result["title"]) > MAX_TITLE_LEN:
            result["title"] = result["title"][:MAX_TITLE_LEN].rsplit(" ", 1)[0] or result["title"][:MAX_TITLE_LEN]

        # Rank Math meta title; defaults to the article title if the model omits it.
        seo_title_match = re.search(r'(?:2\.|SEO_TITLE:)\s*(.+?)(?:\n|3\.|META_DESCRIPTION:|---|$)', raw_text, re.IGNORECASE | re.DOTALL)
        if seo_title_match:
            result["seo_title"] = clean_meta(seo_title_match.group(1))
        else:
            result["seo_title"] = result["title"]
        if len(result["seo_title"]) > MAX_TITLE_LEN:
            result["seo_title"] = result["seo_title"][:MAX_TITLE_LEN].rsplit(" ", 1)[0] or result["seo_title"][:MAX_TITLE_LEN]

        # Meta description extracted after the explicit SEO title field.
        meta_match = re.search(r'(?:3\.|META_DESCRIPTION:)\s*(.+?)(?:\n|4\.|SLUG:|---|$)', raw_text, re.IGNORECASE | re.DOTALL)
        if meta_match:
            result["meta_description"] = clean_meta(meta_match.group(1))
        else:
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            if len(lines) > 2 and len(lines[2]) > 50:
                result["meta_description"] = clean_meta(lines[2])
            elif len(lines) > 1 and len(lines[1]) > 50:
                result["meta_description"] = clean_meta(lines[1])
            else:
                result["meta_description"] = result["title"][:155]

        MAX_SLUG_LEN = 50
        slug_match = re.search(r'(?:4\.|SLUG:)\s*([a-z0-9-]+)', raw_text, re.IGNORECASE)
        if slug_match:
            result["slug"] = re.sub(r'-+', '-', clean_meta(slug_match.group(1).lower()).strip('-'))
        else:
            result["slug"] = re.sub(r'[^a-z0-9]+', '-', result["title"].lower()).strip('-')
        result["slug"] = result["slug"][:MAX_SLUG_LEN].rstrip('-')

        tags_match = re.search(r'(?:5\.|TAGS:)\s*(.+?)(?:\n|6\.|CATEGORY:|---|$)', raw_text, re.IGNORECASE | re.DOTALL)
        if tags_match:
            result["tags"] = [clean_meta(t) for t in tags_match.group(1).split(",") if t.strip()]
        else:
            result["tags"] = ["women welfare", "india"]

        category_match = re.search(r'(?:6\.|CATEGORY:)\s*([a-z0-9-]+)', raw_text, re.IGNORECASE)
        result["category"] = clean_meta(category_match.group(1).lower()) if category_match else "news"
        final_kw = matched_keyword if matched_keyword else clean_meta(topic_title)
        result["matched_keyword"] = final_kw
        result["focus_keyword"] = final_kw

        lang_match = re.search(r'(?:7\.|LANG:)\s*([a-z]{2})', raw_text, re.IGNORECASE)
        result["lang"] = clean_meta(lang_match.group(1).lower()) if lang_match else "en"

        content_block_match = re.search(r'---CONTENT_START---(.*?)---CONTENT_END---', raw_text, re.DOTALL)
        if content_block_match:
            result["content"] = content_block_match.group(1).strip()
        else:
            fuzzy_parts = re.split(r'(?:8\.|---CONTENT_START---).*?\n', raw_text, maxsplit=1, flags=re.IGNORECASE | re.DOTALL)
            if len(fuzzy_parts) > 1:
                result["content"] = fuzzy_parts[1].split("---CONTENT_END---")[0].strip()
            else:
                lines = raw_text.split("\n")
                result["content"] = "\n".join(lines[7:]).strip() if len(lines) > 7 else raw_text
        if not result["content"]:
            result["content"] = raw_text

        # Meta description: ensure 140â€“155 chars and attractive (fallback from content if too short)
        md = (result.get("meta_description") or result["title"]).strip()[:155]
        if len(md) < 100 and result["content"]:
            first = result["content"].split(".")[0].strip()[:120]
            if first:
                md = (md + " " + first).strip()[:155]
        result["meta_description"] = md or result["title"][:155]
        if not result.get("seo_title"):
            result["seo_title"] = result["title"]

        # â”€â”€ 7. FAQ â”€â”€ Extract FAQPage schema; keep only if it has real questions (not placeholders)
        result["faq_html"] = ""
        faq_block = re.search(r'---FAQ_START---(.*?)---FAQ_END---', raw_text, re.DOTALL)
        if faq_block:
            result["faq_html"] = re.sub(r'<!--.*?-->', '', faq_block.group(1), flags=re.DOTALL).strip()
        if not result["faq_html"]:
            # Fallback: find any FAQPage JSON-LD script in the response
            schema_match = re.search(
                r'<script\s+type=["\']application/ld\+json["\'].*?FAQPage.*?</script>',
                raw_text, re.DOTALL | re.IGNORECASE
            )
            if schema_match:
                result["faq_html"] = schema_match.group(0).strip()
        if result["faq_html"]:
            stripped_faq = result["faq_html"].strip()
            if not re.search(r'<script\b', stripped_faq, re.IGNORECASE):
                stripped_faq = (
                    '<script type="application/ld+json">\n'
                    + stripped_faq
                    + '\n</script>'
                )
            result["faq_html"] = stripped_faq
        # Reject placeholder-only schema (so we don't publish fake FAQ)
        placeholder_phrases = (
            "Insert Question", "Insert detailed answer", "First real question in full",
            "Second real question?", "Third real question?", "[write actual question]",
            "[Write 2â€“4 sentence answer", "[Write answer.]"
        )
        if result["faq_html"] and any(p in result["faq_html"] for p in placeholder_phrases):
            result["faq_html"] = ""
        # Require at least one real question (name field contains a question ending with ?)
        if result["faq_html"] and '"name":' in result["faq_html"]:
            if not re.search(r'"name":\s*"[^"]*\?"', result["faq_html"]):
                result["faq_html"] = ""

        # â”€â”€ Markdown to HTML â”€â”€
        import markdown

        result["content_html"] = markdown.markdown(
            result["content"],
            extensions=['nl2br', 'sane_lists']
        )

        # â”€â”€ Build FAQ from schema (ALWAYS, as a guarantee) â”€â”€
        # This ensures visible questions even when the AI outputs only plain paragraphs.
        def _build_faq_from_schema(faq_html_str):
            """Parse FAQ JSON-LD schema and return standard HTML with visible questions."""
            import json as _json
            script_body = re.search(r'<script[^>]*>([\s\S]*?)</script>', faq_html_str, re.IGNORECASE)
            if not script_body:
                return None
            data = _json.loads(script_body.group(1).strip())
            entities = data.get("mainEntity") or []
            qa_list = []
            for ent in entities:
                if not isinstance(ent, dict):
                    continue
                name = (ent.get("name") or "").strip()
                ans = ent.get("acceptedAnswer") or {}
                text = (ans.get("text") if isinstance(ans, dict) else "") or ""
                if name and "?" in name:
                    qa_list.append((name, text))
            if not qa_list:
                return None
            parts = []
            for q, a in qa_list:
                q_esc = (q or "").replace("<", "&lt;").replace(">", "&gt;").strip()
                a_esc = (a or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                parts.append(f'<!-- wp:heading {{"level":3}} -->\n<h3>{q_esc}</h3>\n<!-- /wp:heading -->')
                parts.append(f'<!-- wp:paragraph -->\n<p>{a_esc}</p>\n<!-- /wp:paragraph -->')
            return "\n".join(parts)

        # Check if content already has properly formed FAQ headings
        has_visible_faq = bool(re.search(
            r'<h[234][^>]*>[^<]*\?[^<]*</h[234]>',
            result["content_html"]
        ))

        if not has_visible_faq and result.get("faq_html") and "FAQPage" in result["faq_html"]:
            try:
                faq_list_html = _build_faq_from_schema(result["faq_html"])
                if faq_list_html:
                    # Find FAQ heading and replace everything after it with the proper list
                    faq_heading_match = re.search(
                        r'(<h2[^>]*>.*?Frequently Asked Questions.*?</h2>)',
                        result["content_html"],
                        re.IGNORECASE | re.DOTALL
                    )
                    if faq_heading_match:
                        start = result["content_html"].find(faq_heading_match.group(0))
                        new_section = faq_heading_match.group(0) + "\n\n" + faq_list_html
                        result["content_html"] = result["content_html"][:start] + new_section
                    else:
                        result["content_html"] += "\n\n<!-- wp:heading {\"level\":2} -->\n<h2>Frequently Asked Questions</h2>\n<!-- /wp:heading -->\n\n" + faq_list_html
                    logger.info("  âœ… FAQ list rebuilt from schema (questions now visible)")
            except Exception as faq_e:
                logger.debug(f"FAQ list build failed: {faq_e}")

        # Assembly: wrap body in padded container (medium padding on all sides, below featured image)
        PADDING_STYLE = "padding: 1.5rem;"
        wrapped_body = (
            f'<div class="women-article-body entry-content-wrap" style="{PADDING_STYLE}">'
            f"\n{result['content_html']}\n</div>"
        )

        # FAQ schema: in Gutenberg Custom HTML block; hidden so it never shows as text (Google still reads it)
        faq_block_output = ""
        if result["faq_html"]:
            hidden_schema = (
                '<div class="women-faq-schema" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);clip-path:inset(50%);white-space:nowrap;" aria-hidden="true">'
                + result["faq_html"]
                + "</div>"
            )
            faq_block_output = "\n\n<!-- wp:html -->\n" + hidden_schema + "\n<!-- /wp:html -->"

        result["full_content"] = wrapped_body + faq_block_output

        return result

    except Exception as e:
        logger.exception("  âŒ Parse error")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_topic = {
        "topic": "Ladli Behna Yojana Payment Status 2026",
        "matched_keyword": "ladli-behna-yojana",
        "stories": [{"summary": "Latest updates on women empowerment schemes and beneficiary support."}]
    }
    article = generate_article(test_topic)
    if article:
        print(f"TITLE: {article['title']}")
        print(f"CONTENT PREVIEW: {article['full_content'][:500]}...")





