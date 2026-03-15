"""
News Site Scraper — Searches Google for government scheme keywords on target news sites.
If a keyword/topic appears on >= NEWS_SITE_MIN_COVERAGE of the monitored domains,
it is flagged as a high-confidence recommendation.

Uses Google search with `site:domain query` to find recent coverage.
Results are fed into the main scan pipeline as stories.
"""
import hashlib
import logging
import re
import time
import urllib.parse
from datetime import datetime

import requests

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from detection.scheme_registry import get_trends_keywords

logger = logging.getLogger(__name__)

# Google search URL (no API key needed — uses standard web search)
_GOOGLE_SEARCH_URL = "https://www.google.com/search"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
}
_REQUEST_TIMEOUT = 12
_DELAY_BETWEEN_REQUESTS = 3  # seconds, be polite to Google


def _hash_story(title, url):
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _extract_result_urls(html_text):
    """Extract result URLs from Google search result HTML."""
    urls = []
    # Match href patterns in Google results
    for match in re.finditer(r'href="/url\?q=([^&"]+)', html_text):
        url = urllib.parse.unquote(match.group(1))
        if url.startswith("http") and "google.com" not in url:
            urls.append(url)
    # Also match direct href links
    for match in re.finditer(r'href="(https?://[^"]+)"', html_text):
        url = match.group(1)
        if "google.com" not in url and url not in urls:
            urls.append(url)
    return urls


def _extract_result_titles(html_text):
    """Extract result titles from Google search result HTML (simplified)."""
    titles = []
    # Match <h3> tags which typically contain result titles
    for match in re.finditer(r'<h3[^>]*>(.*?)</h3>', html_text, re.DOTALL):
        title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        if title and len(title) > 10:
            titles.append(title)
    return titles


def _search_google(query, num_results=10):
    """Perform a Google search and return list of (title, url) tuples."""
    params = {
        "q": query,
        "num": num_results,
        "hl": "en",
        "gl": "in",
        "tbs": "qdr:d",  # Past 24 hours
    }
    try:
        resp = requests.get(
            _GOOGLE_SEARCH_URL, params=params, headers=_HEADERS,
            timeout=_REQUEST_TIMEOUT, allow_redirects=True,
        )
        if resp.status_code != 200:
            logger.warning(f"Google search returned {resp.status_code} for query: {query[:60]}")
            return []

        html = resp.text
        urls = _extract_result_urls(html)
        titles = _extract_result_titles(html)

        results = []
        for i, url in enumerate(urls[:num_results]):
            title = titles[i] if i < len(titles) else query
            results.append((title, url))
        return results

    except Exception as e:
        logger.warning(f"Google search error for '{query[:60]}': {e}")
        return []


def _build_search_queries():
    """Build search queries from scheme names + filter phrases."""
    filter_phrases = getattr(config, "REQUIRED_KEYWORD_PHRASES", [])
    scheme_keywords = get_trends_keywords(limit=20)

    # Add key Hindi/Marathi equivalents for multilingual coverage
    multilingual_phrases = [
        "किस्त तारीख", "किस्त जारी", "हप्ता तारीख", "योजना अपडेट",
        "ई-केवाईसी", "eKYC", "किश्त", "योजना",
    ]

    queries = []
    seen = set()

    # Combine top scheme keywords with filter phrases
    for scheme in scheme_keywords[:15]:
        for phrase in filter_phrases[:6]:  # Top 6 phrases to keep requests reasonable
            q = f"{scheme} {phrase}"
            key = q.lower().strip()
            if key not in seen:
                seen.add(key)
                queries.append(q)

    # Add Hindi/Marathi queries for multilingual coverage
    hindi_schemes = [
        "लाडली बहना योजना", "पीएम किसान", "लाडकी बहीण योजना",
        "महतारी वंदन योजना", "सुभद्रा योजना", "नमो शेतकरी योजना",
    ]
    for scheme in hindi_schemes:
        for phrase in multilingual_phrases[:4]:
            q = f"{scheme} {phrase}"
            key = q.lower().strip()
            if key not in seen:
                seen.add(key)
                queries.append(q)

    return queries


def _count_site_coverage(query, sites):
    """Search Google for a query and count how many of the target sites have results."""
    results = _search_google(query, num_results=20)
    if not results:
        return 0, []

    covered_sites = set()
    matched_articles = []
    for title, url in results:
        url_lower = url.lower()
        for site in sites:
            if site.lower() in url_lower:
                covered_sites.add(site)
                matched_articles.append({
                    "title": title,
                    "url": url,
                    "site": site,
                })
                break

    return len(covered_sites), matched_articles


def scan_news_sites():
    """
    Scan target news sites for government scheme topics matching the filter.
    Returns list of story dicts compatible with the main pipeline.

    Topics found on >= NEWS_SITE_MIN_COVERAGE sites get a higher spike score.
    """
    sites = getattr(config, "NEWS_MONITOR_SITES", [])
    min_coverage = getattr(config, "NEWS_SITE_MIN_COVERAGE", 3)

    if not sites:
        logger.info("News Site Scraper: No sites configured, skipping")
        return []

    queries = _build_search_queries()
    if not queries:
        logger.info("News Site Scraper: No search queries built, skipping")
        return []

    logger.info(f"News Site Scraper: Scanning {len(queries)} queries across {len(sites)} sites")

    stories = []
    high_confidence_topics = []
    queries_checked = 0
    max_queries = 30  # Limit to avoid excessive Google requests

    for query in queries[:max_queries]:
        try:
            coverage_count, articles = _count_site_coverage(query, sites)
            queries_checked += 1

            if coverage_count >= min_coverage:
                logger.info(
                    f"  HIGH CONFIDENCE: '{query[:60]}' found on {coverage_count}/{len(sites)} sites"
                )
                high_confidence_topics.append({
                    "query": query,
                    "coverage_count": coverage_count,
                    "articles": articles,
                })

                # Add each article as a story for the pipeline
                for art in articles:
                    story_hash = _hash_story(art["title"], art["url"])
                    stories.append({
                        "title": art["title"],
                        "summary": f"Found on {coverage_count} major news sites: {query}",
                        "url": art["url"],
                        "source": f"NewsSite/{art['site']}",
                        "source_type": "news_site_scraper",
                        "matched_keyword": query,
                        "published_at": datetime.utcnow(),
                        "story_hash": story_hash,
                        "is_rising": True,
                        "site_coverage": coverage_count,
                    })
            elif coverage_count > 0:
                logger.debug(f"  Low coverage: '{query[:60]}' on {coverage_count} sites")
                # Still add as stories but without the high-confidence flag
                for art in articles:
                    story_hash = _hash_story(art["title"], art["url"])
                    stories.append({
                        "title": art["title"],
                        "summary": f"Found on {coverage_count} news sites: {query}",
                        "url": art["url"],
                        "source": f"NewsSite/{art['site']}",
                        "source_type": "news_site_scraper",
                        "matched_keyword": query,
                        "published_at": datetime.utcnow(),
                        "story_hash": story_hash,
                        "is_rising": False,
                        "site_coverage": coverage_count,
                    })

            time.sleep(_DELAY_BETWEEN_REQUESTS)

        except Exception as e:
            logger.warning(f"News Site Scraper error for '{query[:60]}': {e}")
            continue

    # Deduplicate by story_hash
    seen_hashes = set()
    unique_stories = []
    for story in stories:
        if story["story_hash"] not in seen_hashes:
            seen_hashes.add(story["story_hash"])
            unique_stories.append(story)

    logger.info(
        f"News Site Scraper: {queries_checked} queries checked, "
        f"{len(high_confidence_topics)} high-confidence topics, "
        f"{len(unique_stories)} unique stories"
    )
    return unique_stories
