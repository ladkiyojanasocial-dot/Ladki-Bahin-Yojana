"""
Central configuration for the Women Empowerment Alerts App.
All settings, keywords, RSS feeds, and thresholds are defined here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from detection.scheme_registry import build_watchlist_keywords

# Load .env from project root so it works regardless of current working directory
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env")

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
_newsapi_keys_list = []
for env_name in ("NEWS_API_KEYS", "NEWS_API_KEY"):
    val = os.getenv(env_name, "").strip()
    if not val:
        continue
    for k in val.split(","):
        k = k.strip()
        if k and k not in _newsapi_keys_list:
            _newsapi_keys_list.append(k)
NEWS_API_KEYS = _newsapi_keys_list
NEWS_API_KEY = NEWS_API_KEYS[0] if NEWS_API_KEYS else None

# Collect all Gemini keys for rotation. Legacy single-key envs are still accepted if present.
_gemini_keys_list = []
for env_name in ("GEMINI_API_KEYS", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
    val = os.getenv(env_name, "").strip()
    if not val:
        continue
    for k in val.split(","):
        k = k.strip()
        if k and k not in _gemini_keys_list:
            _gemini_keys_list.append(k)
GEMINI_API_KEYS = _gemini_keys_list
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else None

WP_URL = os.getenv("WP_URL", "https://womenempowermentportal.org")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
WP_PUBLISH_WEBHOOK_URL = os.getenv("WP_PUBLISH_WEBHOOK_URL", "").strip()
WP_PUBLISH_SECRET = os.getenv("WP_PUBLISH_SECRET", "").strip()
APP_STATE_NAMESPACE = os.getenv("APP_STATE_NAMESPACE", "ladki-bahin-agent").strip() or "ladki-bahin-agent"
# Optional: Unsplash API for high-quality stock photos (50 req/hr free). If set, we try Unsplash before AI image gen.
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "").strip() or None

# RSS Feeds
RSS_FEEDS = {
    "PIB Press Releases": "https://pib.gov.in/RssMain.aspx?ModId=6&LangId=1",
    "ET Economy": "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
    "ET Industry": "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms",
    "ET India News": "https://economictimes.indiatimes.com/news/india/rssfeeds/81582957.cms",
    "Indian Express India": "https://indianexpress.com/section/india/feed/",
    "Indian Express Economy": "https://indianexpress.com/section/business/economy/feed/",
    "Indian Express Lifestyle": "https://indianexpress.com/section/lifestyle/feed/",
    "Zee News Nation": "https://zeenews.india.com/rss/india-national-news.xml",
    "Zee News States": "https://zeenews.india.com/rss/india-news.xml",
    "Zee News Lifestyle": "https://zeenews.india.com/rss/lifestyle-news.xml",
    "Hindustan Times India": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
    "Hindustan Times Economy": "https://www.hindustantimes.com/feeds/rss/ht-insight/economy/rssfeed.xml",
    "Livemint Economy & Politics": "https://www.livemint.com/rss/economy_politics",
    "NDTV Business": "https://feeds.feedburner.com/ndtvkhabar-business",
    "Swarajya Magazine": "https://swarajyamag.com/rss",
}

# Keep empty so all feeds must pass keyword filtering.
AGRI_ONLY_FEEDS = []

# Keyword Watchlists
CENTRAL_SCHEMES = [
    "Beti Bachao Beti Padhao", "BBBP",
    "Sukanya Samriddhi Yojana", "SSY",
    "Pradhan Mantri Matru Vandana Yojana", "PMMVY",
    "Ujjwala Yojana", "PMUY",
    "One Stop Centre", "Sakhi Centre",
    "Working Women Hostel",
    "STEP Scheme", "Support to Training and Employment Programme for Women",
    "Mahila Samman Savings Certificate", "MSSC",
    "Lakhpati Didi", "Namo Drone Didi",
    "Stand Up India Women Loan", "MUDRA Women",
    "PM Vishwakarma Women",
    "Women SHG", "Self Help Group",
]

STATE_SCHEMES = [
    "Ladli Behna Yojana", "Ladli Bahan",
    "Ladli Laxmi Yojana",
    "Majhi Ladki Bahin Yojana", "Mukhyamantri Majhi Ladki Bahin",
    "Gruha Lakshmi Yojana",
    "Kanyashree Prakalpa",
    "Subhadra Yojana Odisha",
    "Mahtari Vandan Yojana",
    "Kalaignar Magalir Urimai Thogai",
    "Nanda Gaura Yojana",
    "Mukhyamantri Kanya Utthan Yojana",
]

GENERAL_AGRI_KEYWORDS = [
    "Women Empowerment", "Mahila Yojana", "Mahila Kalyan",
    "Women Welfare", "Girl Child Scheme", "Women Safety Scheme",
    "Women Entrepreneurship", "Women Loan Scheme",
    "Self Help Group", "SHG Loan", "NRLM Women",
    "Women Skill Development", "Women Training Program",
    "Scholarship for Girls", "Girl Education Scheme",
    "Women Helpline", "Mahila Helpline",
    "Women Pension Scheme", "Widow Pension Women",
    "Women Financial Assistance", "Direct Benefit Transfer Women",
    "Women Portal", "Mahila Portal",
    "Kanya Vivah Yojana", "Kanya Protsahan",
    "Women Startup India", "Nari Shakti",
]

EXCLUDE_KEYWORDS = [
    "football", "soccer", "world cup",
    "cricket", "t20", "ipl", "odi", "test match",
    "icc", "wpl", "tennis", "rugby", "f1", "golf",
    "bollywood", "movie review", "box office", "celebrity",
    "election campaign", "political rally", "stock market rally",
    "crypto", "bitcoin",
]

# Combined master list for filtering
ALL_KEYWORDS = CENTRAL_SCHEMES + STATE_SCHEMES + GENERAL_AGRI_KEYWORDS

# Merge master registry aliases to avoid missing schemes/topics in monitoring.
for _kw in build_watchlist_keywords():
    if _kw not in ALL_KEYWORDS:
        ALL_KEYWORDS.append(_kw)

HIGH_VALUE_AGRI_KEYWORDS = [
    "installment", "instalment", "ekyc", "e-kyc", "eKYC", "last date", "deadline",
    "eligibility", "status check", "new scheme", "enrollment", "enrolment",
    "how to apply", "beneficiary", "released", "announced", "registration",
    "extended", "apply online", "portal", "mahila", "ladli", "kanya",
    "rule change", "new rule", "guideline change", "updated", "revised",
    "notification", "gazette", "circular", "amendment",
    "increased", "hiked", "reduced", "disbursed", "credited",
    "beneficiary list", "rejection", "rejected", "ineligible",
    "aadhaar link", "bank link", "income certificate", "residence certificate",
    "direct benefit transfer", "DBT", "payment status",
    "loan approval", "scheme renewal",
    "subsidy amount", "subsidy rate", "interest rate",
    "kist", "kist date", "next installment",
]

CONTENT_IDEAS = [
    {"topic": "Ladli Behna Yojana 2026: Eligibility and Payment Status Check", "matched_keyword": "Ladli Behna Yojana"},
    {"topic": "Ladli Behna eKYC Update: How to Verify and Avoid Payment Hold", "matched_keyword": "Ladli Behna Yojana"},
    {"topic": "Majhi Ladki Bahin Yojana: Registration Process and Required Documents", "matched_keyword": "Majhi Ladki Bahin Yojana"},
    {"topic": "Majhi Ladki Bahin Installment Date 2026: Latest Update and Status", "matched_keyword": "Majhi Ladki Bahin Yojana"},
    {"topic": "Subhadra Yojana Odisha: Who Is Eligible and How to Apply Online", "matched_keyword": "Subhadra Yojana Odisha"},
    {"topic": "Subhadra Yojana Beneficiary List 2026: Step-by-Step Name Check", "matched_keyword": "Subhadra Yojana Odisha"},
    {"topic": "Gruha Lakshmi Yojana Karnataka: Amount, Status, and eKYC Guide", "matched_keyword": "Gruha Lakshmi Yojana"},
    {"topic": "Gruha Lakshmi Payment Not Received: Common Reasons and Fixes", "matched_keyword": "Gruha Lakshmi Yojana"},
    {"topic": "Mahtari Vandan Yojana: Eligibility, Documents, and Payment Status", "matched_keyword": "Mahtari Vandan Yojana"},
    {"topic": "Kalaignar Magalir Urimai Thogai: Monthly Benefit and Application Guide", "matched_keyword": "Kalaignar Magalir Urimai Thogai"},
    {"topic": "Kanyashree Prakalpa 2026: Application, Renewal, and Scholarship Status", "matched_keyword": "Kanyashree Prakalpa"},
    {"topic": "Ladli Laxmi Yojana Benefits: Full Stage-Wise Financial Support", "matched_keyword": "Ladli Laxmi Yojana"},
    {"topic": "Mukhyamantri Kanya Utthan Yojana: Eligibility and Online Apply Steps", "matched_keyword": "Mukhyamantri Kanya Utthan Yojana"},
    {"topic": "Nanda Gaura Yojana: Eligibility and Benefit Amount 2026", "matched_keyword": "Nanda Gaura Yojana"},
    {"topic": "Beti Bachao Beti Padhao: Latest Guidelines and District Implementation", "matched_keyword": "Beti Bachao Beti Padhao"},
    {"topic": "Sukanya Samriddhi Yojana Interest Rate 2026 and Account Opening Rules", "matched_keyword": "Sukanya Samriddhi Yojana"},
    {"topic": "Pradhan Mantri Matru Vandana Yojana: Eligibility and Payment Process", "matched_keyword": "Pradhan Mantri Matru Vandana Yojana"},
    {"topic": "PMMVY Status Check 2026: How Beneficiaries Can Track Installments", "matched_keyword": "Pradhan Mantri Matru Vandana Yojana"},
    {"topic": "Ujjwala Yojana Refill Subsidy 2026: Latest Rules and Eligibility", "matched_keyword": "Ujjwala Yojana"},
    {"topic": "Mahila Samman Savings Certificate: Interest Rate and Maturity Guide", "matched_keyword": "Mahila Samman Savings Certificate"},
    {"topic": "STEP Scheme for Women: Training Courses and Enrollment Process", "matched_keyword": "STEP Scheme"},
    {"topic": "Working Women Hostel Scheme: Who Can Apply and How to Get Admission", "matched_keyword": "Working Women Hostel"},
    {"topic": "One Stop Centre Services: How Women Can Access Legal and Medical Help", "matched_keyword": "One Stop Centre"},
    {"topic": "Stand Up India Women Loan: Eligibility, Interest Rate, and Documents", "matched_keyword": "Stand Up India Women Loan"},
    {"topic": "MUDRA Loan for Women Entrepreneurs: How to Apply and Repay", "matched_keyword": "MUDRA Women"},
    {"topic": "Women SHG Loan 2026: Interest, Repayment, and Subsidy Support", "matched_keyword": "Women SHG"},
    {"topic": "Lakhpati Didi Scheme: How SHG Women Can Build Sustainable Income", "matched_keyword": "Lakhpati Didi"},
    {"topic": "Namo Drone Didi Scheme: Training and Earning Opportunities for Women", "matched_keyword": "Namo Drone Didi"},
    {"topic": "Top Women Empowerment Schemes in India 2026: Central and State List", "matched_keyword": "Women Empowerment"},
    {"topic": "How to Check Any Women Welfare Scheme Status Online: Complete Guide", "matched_keyword": "Women Welfare"},
    {"topic": "Women Scheme Rejected? Common Reasons and Document Correction Steps", "matched_keyword": "Mahila Yojana"},
    {"topic": "Aadhaar and Bank Seeding for Women Schemes: Why It Matters", "matched_keyword": "Mahila Yojana"},
    {"topic": "Best Government Schemes for Women Entrepreneurs in 2026", "matched_keyword": "Women Entrepreneurship"},
    {"topic": "Girl Child Schemes in India: Eligibility, Amount, and Application Links", "matched_keyword": "Girl Child Scheme"},
    {"topic": "Women Safety and Support Helplines: National and State Guide", "matched_keyword": "Women Helpline"},
]

# Detection Settings
SPIKE_THRESHOLD = 2.0
SPIKE_MIN_SCORE = 25
ROLLING_WINDOW_HOURS = 24
SCAN_INTERVAL_MINUTES = 60
DEDUP_WINDOW_HOURS = 72
BREAKING_SPIKE_SCORE = 95
MIN_COVERAGE_TOPICS_PER_CYCLE = 4
MAX_REFRESH_TOPICS_PER_CYCLE = 2
AUTO_GENERATE_BREAKING = False
REQUIRE_ARTICLE_CONFIRMATION = True

# Google Trends Settings
TRENDS_GEO = "IN"
TRENDS_KEYWORDS_PER_BATCH = 5
TRENDS_KEYWORDS_PER_CYCLE = 25
TRENDS_KEYWORDS_MAX = 60
NEWSAPI_ROTATING_QUERY_COUNT = 1

# WordPress Settings
WP_DEFAULT_CATEGORY = "Uncategorized"
WP_DEFAULT_STATUS = "draft"

# Article Generation Settings
ARTICLE_MIN_WORDS = 800
ARTICLE_MAX_WORDS = 1500
GEMINI_MODEL = "gemini-2.5-flash"
IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
SKIP_AI_IMAGE = os.getenv("SKIP_AI_IMAGE", "false").lower() in ("true", "1", "yes")
USE_GEMINI_IMAGEN = os.getenv("USE_GEMINI_IMAGEN", "false").lower() in ("true", "1", "yes")
USE_PLACEHOLDER_IMAGE = os.getenv("USE_PLACEHOLDER_IMAGE", "false").lower() in ("true", "1", "yes")
USE_GEMINI_FLASH_IMAGE = os.getenv("USE_GEMINI_FLASH_IMAGE", "true").lower() in ("true", "1", "yes")
IMAGE_GEMINI_FLASH_RETRIES = max(0, int(os.getenv("IMAGE_GEMINI_FLASH_RETRIES", "0")))
IMAGE_POLLINATIONS_TIMEOUT_SECONDS = max(10, int(os.getenv("IMAGE_POLLINATIONS_TIMEOUT_SECONDS", "20")))

# Logging
LOG_FILE = "agent.log"
LOG_LEVEL = "INFO"
