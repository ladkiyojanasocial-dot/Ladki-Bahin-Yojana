"""
SEO Prompt Template - Master prompt used for Gemini article generation.
Enforces SEO best practices, your site's editorial style, Kadence block HTML, and internal linking.
"""
import os
import json
from urllib.parse import urlparse
from detection.scheme_registry import get_category_slug_for_text, get_authority_url_for_text

SCHEME_CATEGORY_SLUGS = [
    "ladli-behna-yojana", "majhi-ladki-bahin-yojana", "subhadra-yojana",
    "gruha-lakshmi-yojana", "mahtari-vandan-yojana", "kanyashree-prakalpa",
    "ladli-laxmi-yojana", "mukhyamantri-kanya-utthan-yojana",
    "beti-bachao-beti-padhao", "sukanya-samriddhi-yojana",
    "pradhan-mantri-matru-vandana-yojana", "ujjwala-yojana",
    "mahila-samman-savings-certificate", "step-scheme-women",
    "one-stop-centre-scheme", "working-women-hostel-scheme",
    "lakhpati-didi-scheme", "namo-drone-didi-scheme",
]
CATEGORY_MAPPING = SCHEME_CATEGORY_SLUGS + ["news"]

KEYWORDS_TO_CATEGORY = [
    (["ladli behna", "ladli bahan"], "ladli-behna-yojana"),
    (["majhi ladki bahin", "ladki bahin yojana"], "majhi-ladki-bahin-yojana"),
    (["subhadra yojana"], "subhadra-yojana"),
    (["gruha lakshmi", "gruhalakshmi"], "gruha-lakshmi-yojana"),
    (["mahtari vandan", "mahatari vandan"], "mahtari-vandan-yojana"),
    (["kanyashree"], "kanyashree-prakalpa"),
    (["ladli laxmi"], "ladli-laxmi-yojana"),
    (["kanya utthan"], "mukhyamantri-kanya-utthan-yojana"),
    (["beti bachao beti padhao", "bbbp"], "beti-bachao-beti-padhao"),
    (["sukanya samriddhi", "ssy"], "sukanya-samriddhi-yojana"),
    (["matru vandana", "pmmvy"], "pradhan-mantri-matru-vandana-yojana"),
    (["ujjwala", "pmuy"], "ujjwala-yojana"),
    (["mahila samman", "mssc"], "mahila-samman-savings-certificate"),
    (["step scheme"], "step-scheme-women"),
    (["one stop centre", "sakhi centre"], "one-stop-centre-scheme"),
    (["working women hostel"], "working-women-hostel-scheme"),
    (["lakhpati didi"], "lakhpati-didi-scheme"),
    (["namo drone didi", "drone didi"], "namo-drone-didi-scheme"),
]


def get_category_for_topic(topic_title, matched_keyword=""):
    """Return WordPress category slug from master scheme registry; fallback to static mapping."""
    if not topic_title and not matched_keyword:
        return "news"

    slug = get_category_slug_for_text(topic_title, matched_keyword)
    if slug and slug != "news":
        return slug

    combined = f" {((topic_title or '') + ' ' + (matched_keyword or '')).lower()} "
    for phrases, static_slug in KEYWORDS_TO_CATEGORY:
        for phrase in phrases:
            if phrase.lower() in combined:
                return static_slug
    return "news"


BASE_URL = os.getenv("WP_URL", "https://womenempowermentportal.org").rstrip("/")

PUBLISHED_POSTS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "published_posts.json")


def _load_published_posts():
    if not os.path.exists(PUBLISHED_POSTS_FILE):
        return []
    try:
        with open(PUBLISHED_POSTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = []
        for entry in data:
            url = (entry.get("url") or "").strip()
            if not url or not url.startswith("http"):
                continue
            title = (entry.get("title") or "").strip() or "Article"
            slug = (entry.get("slug") or "").strip()
            anchors = [title]
            if slug:
                anchors.append(slug.replace("-", " "))
            out.append({"url": url.rstrip("/") + "/", "topic": title, "anchors": anchors})
        return out
    except Exception:
        return []


def get_internal_links_for_prompt():
    try:
        from publisher.wordpress_client import get_site_keyword_inventory
        inventory = get_site_keyword_inventory()
        posts = inventory.get("posts", []) if isinstance(inventory, dict) else []
        live_links = []
        seen = set()
        for post in posts:
            url = (post.get("url") or "").strip()
            if not url.startswith("http"):
                continue
            if BASE_URL and not url.startswith(BASE_URL.rstrip("/")):
                continue
            key = url.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            title = (post.get("title") or "").strip() or "Article"
            slug = (post.get("slug") or "").strip()
            anchors = [title]
            if slug:
                anchors.append(slug.replace("-", " "))
            live_links.append({"url": key + "/", "topic": title, "anchors": anchors})
        if live_links:
            return live_links[:20]
    except Exception:
        pass
    return _load_published_posts()


def _build_internal_link_instructions(internal_links):
    if len(internal_links) >= 2:
        return "- You MUST include exactly 2 to 3 internal links inside the body text."
    if len(internal_links) == 1:
        return "- You MUST include exactly 1 internal link inside the body text."
    return "- Do not add any internal links unless a live published URL is listed below."


def _build_internal_link_critical_note(internal_links):
    if len(internal_links) >= 2:
        return "CRITICAL: Include at least 2 internal links in the final article body, and use only live published URLs from the list."
    if len(internal_links) == 1:
        return "CRITICAL: Include the single live internal link listed below if it is relevant."
    return "CRITICAL: Do not invent internal links. If no live internal URL is listed, leave internal links out."


def _is_preferred_official_url(url):
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    return any(token in host for token in ("gov.in", ".gov", "nic.in", "india.gov.in"))


def get_outbound_links_for_prompt(source_texts, topic_title="", matched_keyword=""):
    preferred = []
    seen = set()
    for src in source_texts[:8]:
        url = (src.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        if BASE_URL and BASE_URL.rstrip("/") in url.rstrip("/"):
            continue
        if url in seen:
            continue
        if not _is_preferred_official_url(url):
            continue
        seen.add(url)
        domain = (src.get("source_domain") or urlparse(url).netloc or "Official source").strip()
        preferred.append({"url": url, "label": domain})

    if preferred:
        return preferred[:5]

    authority_url = get_authority_url_for_text(topic_title, matched_keyword)
    if authority_url:
        return [{"url": authority_url, "label": "Government authority"}]
    return []


def add_published_post(post_url, title, slug="", published_at="", focus_keyword=""):
    if not post_url or not title:
        return
    post_url = (post_url or "").strip().rstrip("/")
    if not post_url.startswith("http"):
        return
    try:
        data = []
        if os.path.exists(PUBLISHED_POSTS_FILE):
            with open(PUBLISHED_POSTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        existing_urls = {e.get("url", "").rstrip("/") for e in data}
        if post_url.rstrip("/") in existing_urls:
            return
        data.append({
            "url": post_url,
            "title": (title or "").strip()[:200],
            "slug": (slug or "").strip()[:100],
            "focus_keyword": (focus_keyword or "").strip()[:200],
            "published_at": (published_at or "")[:40],
        })
        with open(PUBLISHED_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        inventory_cache = os.path.join(os.path.dirname(os.path.dirname(__file__)), "site_keyword_inventory.json")
        if os.path.exists(inventory_cache):
            try:
                os.remove(inventory_cache)
            except OSError:
                pass
    except Exception:
        pass


def infer_content_template(topic_title, content_angle=""):
    """Map topic intent to a stable article template."""
    angle = (content_angle or "").strip().lower()
    title = (topic_title or "").strip().lower()
    combined = f"{angle} {title}"

    if any(token in combined for token in ["installment", "kist", "payment release", "payment update", "amount credited"]):
        return "installment_update"
    if any(token in combined for token in ["ekyc", "e-kyc", "e kyc", "kyc update"]):
        return "ekyc_update"
    if any(token in combined for token in ["status", "beneficiary list", "payment status", "application status", "check online"]):
        return "status_check"
    if any(token in combined for token in ["eligibility", "eligible", "how to apply", "application process", "documents required"]):
        return "eligibility_guide"
    if any(token in combined for token in ["breaking", "latest news", "announcement", "released", "deadline extended", "government decision"]):
        return "breaking_news"
    return "generic_guide"


TEMPLATE_LABELS = {
    "installment_update": "Installment Update",
    "ekyc_update": "eKYC Update",
    "status_check": "Status Check",
    "eligibility_guide": "Eligibility Guide",
    "breaking_news": "Breaking News",
    "generic_guide": "General Scheme Guide",
}


def get_template_rules(template_name, primary_keyword):
    rules = {
        "installment_update": f"""
CONTENT TEMPLATE RULES: INSTALLMENT UPDATE
- Focus on installment date, expected amount, beneficiary impact, and official status.
- The intro should say whether the installment is released, expected, delayed, or under verification.
- Add clear sections for release date, amount, eligibility for this installment, status check steps, and common payment failure reasons.
- Use headings similar to: "{primary_keyword} installment date", "who will get payment", "how to check status", and "why payment may be delayed".
- FAQ should cover installment date, amount, status check, and payment not received.
""",
        "ekyc_update": f"""
CONTENT TEMPLATE RULES: EKYC UPDATE
- Focus on whether eKYC is mandatory, deadline, who needs to do it, and what happens if it is not completed.
- Add clear sections for eKYC last date, online and offline eKYC steps, required documents, and common OTP/Aadhaar issues.
- Use headings similar to: "{primary_keyword} eKYC last date", "how to complete eKYC", and "common eKYC issues".
- FAQ should cover mandatory status, last date, OTP problems, and failed verification.
""",
        "status_check": f"""
CONTENT TEMPLATE RULES: STATUS CHECK
- Focus on the exact steps to check status, where to click, what details are needed, and what each result means.
- Add clear sections for official portal, step-by-step status check, meaning of common status messages, and next action if status is pending or rejected.
- Use headings similar to: "how to check {primary_keyword} status", "status meanings", and "what to do if status is pending".
- FAQ should cover portal link, required details, pending status, and rejected status.
""",
        "eligibility_guide": f"""
CONTENT TEMPLATE RULES: ELIGIBILITY GUIDE
- Focus on who can apply, who cannot apply, required documents, and practical steps.
- Add clear sections for eligibility criteria, ineligible cases, documents list, application process, and mistakes to avoid.
- Use headings similar to: "{primary_keyword} eligibility", "documents required", and "how to apply".
- FAQ should cover age or income rules, documents, and application mode.
""",
        "breaking_news": f"""
CONTENT TEMPLATE RULES: BREAKING NEWS
- Lead with the key update immediately and explain why it matters to beneficiaries today.
- Add sections for what changed, who is affected, official source details, and what beneficiaries should do next.
- Keep the article factual, fresh, and easy to quote in AI answers.
- Use headings similar to: "what changed", "who is affected", and "next steps for beneficiaries".
- FAQ should cover the update summary, affected users, date, and action steps.
""",
        "generic_guide": f"""
CONTENT TEMPLATE RULES: GENERAL SCHEME GUIDE
- Explain the scheme/update in a practical way with useful sections for benefits, eligibility, steps, and latest guidance.
- Use straightforward H2s that match search intent and keep the article tightly focused on {primary_keyword}.
""",
    }
    return rules.get(template_name, rules["generic_guide"]).strip()


def get_language_rules(target_lang):
    rules = {
        "en": """
LANGUAGE-SPECIFIC SEO RULES: ENGLISH
- Write in simple Indian English that sounds helpful, not robotic.
- Put the main keyword naturally in the title, meta, first paragraph, and one H2.
- Prefer direct search phrases such as status check, installment date, last date, eligibility, and documents required.
- Keep sentences crisp so AI summaries can quote them cleanly.
""",
        "hi": """
LANGUAGE-SPECIFIC SEO RULES: HINDI
- Write in clear, natural Devanagari Hindi for women beneficiaries. Avoid heavy Hinglish.
- Keep official scheme names in their official form, but explain the update in simple Hindi.
- Put the main keyword naturally in the title, meta, first paragraph, and one H2 in Hindi usage form.
- Use familiar Hindi search phrases such as स्टेटस चेक, किस्त, लाभार्थी सूची, पात्रता, दस्तावेज, आवेदन प्रक्रिया.
- Keep wording easy enough for voice search and AI summaries.
""",
        "te": """
LANGUAGE-SPECIFIC SEO RULES: TELUGU
- Write in clear, natural Telugu script for women beneficiaries. Avoid mixing too much English unless it is an official portal or scheme term.
- Keep official scheme names accurate, but explain the update in simple Telugu.
- Put the main keyword naturally in the title, meta, first paragraph, and one H2 in Telugu usage form.
- Use familiar Telugu search phrases such as స్టేటస్ చెక్, విడత, అర్హత, దరఖాస్తు విధానం, అవసరమైన పత్రాలు.
- Keep the language conversational, trustworthy, and easy for summaries and voice-style answers.
""",
    }
    return rules.get(target_lang, rules["en"]).strip()


def build_article_prompt(topic_title, source_texts, matched_keyword="", target_lang="en", content_angle=""):
    """Build the master SEO prompt for Gemini article generation."""
    sources_block = ""
    for i, src in enumerate(source_texts[:5], 1):
        sources_block += f"""
--- SOURCE {i} ({src.get('source_domain', 'Unknown')}) ---
URL: {src.get('url', '')}
{src.get('text', '')[:2000]}
"""

    pillars_for_prompt = get_internal_links_for_prompt()
    internal_link_rule = _build_internal_link_instructions(pillars_for_prompt)
    internal_link_critical = _build_internal_link_critical_note(pillars_for_prompt)
    links_context = "ALLOWED INTERNAL LINKS:\n"
    if pillars_for_prompt:
        for p in pillars_for_prompt:
            links_context += f"  - Title: {p['topic']}\n"
            links_context += f"    - EXACT URL TO USE: {p['url']}\n"
            links_context += f"    - Allowed Anchors: {', '.join(p['anchors'])}\n"
    else:
        links_context += "  - No live published internal URLs available right now.\n"

    outbound_links = get_outbound_links_for_prompt(source_texts, topic_title=topic_title, matched_keyword=matched_keyword)
    outbound_context = "ALLOWED OUTBOUND LINKS:\n"
    if outbound_links:
        for row in outbound_links:
            flag = "Preferred official source" if _is_preferred_official_url(row["url"]) else "Authoritative source"
            outbound_context += f"  - {flag}: {row['url']} ({row['label']})\n"
    else:
        outbound_context += "  - No outbound source URLs available from source material.\n"

    cat_mapping_str = ", ".join(CATEGORY_MAPPING)
    primary_keyword = (matched_keyword or topic_title).strip()

    lang_labels = {"en": "English", "hi": "Hindi", "te": "Telugu"}
    target_lang = (target_lang or "en").lower()
    if target_lang not in lang_labels:
        target_lang = "en"

    template_name = infer_content_template(topic_title, content_angle)
    template_label = TEMPLATE_LABELS.get(template_name, "General Scheme Guide")
    template_rules = get_template_rules(template_name, primary_keyword)
    language_rules = get_language_rules(target_lang)

    prompt = f"""You are a world-class SEO strategist and Indian women welfare journalist for {BASE_URL}.
Your mission is to create a highly useful article that ranks in search, answers questions directly, and is suitable for AI overviews, answer engines, and generative search experiences.

TASK: Write a complete, publish-ready guide about: {topic_title}
PRIMARY KEYWORD / FOCUS KEYWORD: {primary_keyword}
TARGET LANGUAGE: {lang_labels[target_lang]} ({target_lang})
CONTENT TEMPLATE: {template_label}

SOURCE MATERIAL
{sources_block}

SEO / AEO / GEO STRATEGY

1. INTERNAL LINKING (STRICT)
{internal_link_rule}
- Use ONLY the exact URLs from the allowed internal links list below.
- Never invent, guess, or modify a URL.
- Format: <a href="EXACT_URL_FROM_LIST">anchor text</a>.
- {links_context}

2. OUTBOUND LINKING (STRICT)
- You MUST include at least 1 outbound link inside the body text.
- You MUST use a government or official portal URL from the allowed outbound list below.
- If the source material does not include one, use the government authority URL provided below.
- Never invent, guess, or modify an outbound URL.
- Format: <a href="EXACT_ALLOWED_OUTBOUND_URL">anchor text</a>.
- {outbound_context}

3. LANGUAGE REQUIREMENT
- The full article content must be in TARGET LANGUAGE only: {lang_labels[target_lang]} ({target_lang}).
- Do not mix languages except official scheme names.
- Set LANG field exactly to: {target_lang}.
- {language_rules}

4. SEO REQUIREMENTS
- PRIMARY KEYWORD / FOCUS KEYWORD is: "{primary_keyword}".
- The TITLE must contain the PRIMARY KEYWORD exactly or the closest exact scheme phrase.
- The META_DESCRIPTION must contain the PRIMARY KEYWORD naturally and include a strong click hook such as latest update, status, installment, last date, amount, eligibility, apply process, documents, or payment update.
- The first 120 words must include the PRIMARY KEYWORD naturally.
- The first paragraph must hook the reader by explaining what changed, why it matters now, and what the beneficiary should do next.
- Use the PRIMARY KEYWORD naturally in at least one H2 and in the closing guidance.
- Keep the article tightly focused on the PRIMARY KEYWORD. Do not drift into generic commentary.

5. AEO / GEO REQUIREMENTS
- Answer the main search query early, clearly, and directly in 2 to 4 sentences near the top.
- Write in a way that can be quoted by AI overviews and answer engines: clear facts, clean phrasing, and no fluff.
- Add question-based subheadings where useful, such as eligibility, status check, installment date, eKYC, documents, amount, or how to apply.
- Use short paragraphs, bullets, and step-based explanations so the article is easy to scan.
- If the topic is a fresh update, clearly mark what is new and what remains unchanged.
- The article structure must match the selected content template.
- {template_rules}

6. DO NOT DO THIS
- Do not mention Google Trends, search volume, spike score, or keyword metrics.
- Do not write filler introductions.
- Do not write generic motivational text.
- Do not invent facts beyond the source material.
- Do not stuff keywords unnaturally.

7. HTML FORMATTING
- Use ## for H2 headers and ### for H3 headers.
- Use * for bulleted lists.
- Bold important scheme terms using **term**.

ARTICLE STRUCTURE
CRITICAL: TITLE is the article H1 and must be a real search-friendly headline.
CRITICAL: SEO_TITLE should be a search-optimized meta title and can differ slightly from the H1 if it improves CTR.
CRITICAL: META_DESCRIPTION should be attractive, factual, and click-worthy.
CRITICAL: The intro must say what changed, who is affected, and what action the reader should take.
CRITICAL: The article must feel helpful for search users first, then strong enough for AI summaries.
{internal_link_critical}
CRITICAL: Include at least 1 government outbound source link in the final article body.

1. TITLE: Maximum 60 characters. Must contain the PRIMARY KEYWORD. No markdown or quotes.
2. SEO_TITLE: Maximum 60 characters. Must contain the PRIMARY KEYWORD naturally. This is the Rank Math meta title.
3. META_DESCRIPTION: 140 to 155 characters. Must contain the PRIMARY KEYWORD naturally and a strong hook.
4. SLUG: 3 to 6 words, lowercase, hyphens only, max 50 chars.
5. TAGS: Exactly 5 tags, comma-separated.
6. CATEGORY: ONE slug from: {cat_mapping_str}. Use "news" only if topic does not match a scheme.
7. LANG: The 2-letter ISO language code of this article's text. Use exactly {target_lang}.
8. ---CONTENT_START---
- Start with a short direct-answer intro of 2 to 4 sentences.
- Follow with well-structured H2/H3 sections that match the selected template.
- Add at least 2 bullet lists where useful.
- Include a short FAQ section at the end with 4 to 6 real questions beneficiaries may ask.
- Keep the tone practical, trustworthy, and easy to understand.
9. ---CONTENT_END---
10. ---FAQ_START---
REQUIRED: Output FAQPage JSON-LD schema with 3 to 4 real questions and real answers.
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {{ "@type": "Question", "name": "What is [write actual question here]?", "acceptedAnswer": {{ "@type": "Answer", "text": "[Write 2 to 4 sentence answer here.]" }} }},
    {{ "@type": "Question", "name": "How do I [write actual question]?", "acceptedAnswer": {{ "@type": "Answer", "text": "[Write answer.]" }} }},
    {{ "@type": "Question", "name": "[Third actual question]?", "acceptedAnswer": {{ "@type": "Answer", "text": "[Write answer.]" }} }}
  ]
}}
</script>
11. ---FAQ_END---

Return ONLY this exact structure:
TITLE: ...
SEO_TITLE: ...
META_DESCRIPTION: ...
SLUG: ...
TAGS: tag1, tag2, tag3, tag4, tag5
CATEGORY: ...
LANG: {target_lang}
---CONTENT_START---
[full article in markdown]
---CONTENT_END---
---FAQ_START---
[FAQPage JSON-LD]
---FAQ_END---
"""
    return prompt


def build_image_prompt(topic_title, article_content_snippet=""):
    """Build a clear, editorial-style prompt for AI image generation."""
    prompt = f"""Professional editorial photograph for an Indian women empowerment news article. Topic: {topic_title}.
Scene: Confident Indian women in a community or administrative setting, natural daylight, photorealistic.
Style: High-quality stock photo, documentary style, no visible text overlays.
Rules: No text, no logos, no watermarks, no cartoons. Landscape orientation, 16:9 suitable for featured image."""

    return prompt
