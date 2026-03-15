"""
Central configuration for the Indian Government Scheme Alerts App.
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

# Used-keywords tracking — prevents duplicate target keywords across posts/pages
USED_KEYWORDS_FILE = os.path.join(str(_PROJECT_ROOT), "used_keywords.json")

# Allowed WordPress categories — posts are assigned to one of these; no new categories are created
ALLOWED_CATEGORIES = [
    "Important Pages",
    "Installment Update",
    "Other Government Schemes",
    "Uncategorized",
]

# ── Required Keyword Phrases ─────────────────────────────────────────────────
# Only topics whose keyword or title contains one of these phrases will be accepted.
REQUIRED_KEYWORD_PHRASES = [
    "installment date", "payment date", "installment released",
    "instalment date", "launch date", "yojana update", "ekyc",
    "release date", "installment expected date", "installment", "yojana",
]

# ── News Site Monitoring ──────────────────────────────────────────────────────
# Target news/blog sites to monitor. If a keyword appears on >= NEWS_SITE_MIN_COVERAGE
# of these sites, it gets a high-confidence recommendation boost.
NEWS_MONITOR_SITES = [
    "news18.com",
    "economictimes.indiatimes.com",
    "business-standard.com",
    "saamtv.com",
    "zeenews.india.com",
    "indianexpress.com",
    "navbharattimes.indiatimes.com",
    "ndtv.com",
    "webdunia.com",
    "amarujala.com",
    "goodreturns.in",
    "livemint.com",
    "newsonair.gov.in",
]
NEWS_SITE_MIN_COVERAGE = 3

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

# ── Keyword Watchlists ────────────────────────────────────────────────────────
# Covers ALL major Indian government schemes (central + state), not limited to women-only.

CENTRAL_SCHEMES = [
    # Women-centric
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
    # Agriculture / Farmer
    "PM Kisan", "PM Kisan Samman Nidhi", "PM Kisan Yojana",
    "PM Fasal Bima Yojana", "PMFBY",
    "Kisan Credit Card", "KCC",
    "PM Kisan Mandhan Yojana",
    # Housing
    "PM Awas Yojana", "PMAY", "Awas Yojana Gramin", "Awas Yojana Urban",
    # Health
    "Ayushman Bharat", "PMJAY", "Ayushman Card",
    # Gas / Subsidy
    "LPG Subsidy", "Ration Card", "PM Garib Kalyan",
    # Financial Inclusion
    "Jan Dhan Yojana", "PMJDY",
    "Atal Pension Yojana", "APY",
    "PM Jeevan Jyoti Bima Yojana", "PMJJBY",
    "PM Suraksha Bima Yojana", "PMSBY",
    # Education / Skill
    "PM Vidya Lakshmi", "National Scholarship Portal",
    "PM Mudra Yojana", "MUDRA Loan",
    # Solar / Energy
    "PM Surya Ghar Yojana", "Rooftop Solar",
    "PM Kusum Yojana",
    # Employment
    "PM Rojgar Mela", "PM Vishwakarma Yojana",
    # Others
    "Lado Laxmi Yojana", "Deen Dayal Lado Lakshmi",
    "Swadhar Yojana",
    "Nari Shakti", "Women Empowerment",
]

STATE_SCHEMES = [
    # Women-centric state schemes
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
    "Laxmi Bhandar",
    "Mukhyamantri Mahila Samman Yojana",
    # Farmer state schemes
    "Rythu Bharosa", "Rythu Bharosa Telangana",
    "Rythu Bandhu", "Rythu Bandhu Telangana",
    "Kalia Yojana", "Kalia Yojana Odisha",
    "Namo Shetkari Yojana", "Namo Shetkari Maha Sanman",
    "Krishak Bandhu", "Krishak Bandhu West Bengal",
    "CM Kisan Kalyan Yojana", "Mukhyamantri Kisan Kalyan Yojana",
    "Annadata Sukhibhava", "Annadata Sukhibhava AP",
    "YSR Rythu Bharosa",
    "Mukhyamantri Yuva Udyami Yojana MP",
    # Other state welfare
    "CM Girl Child Protection Scheme",
    "Mukhyamantri Rajshri Yojana",
    "Deen Dayal Lado Lakshmi Yojana",
]

GENERAL_SCHEME_KEYWORDS = [
    # Broad scheme monitoring
    "Government Scheme", "Sarkari Yojana",
    "Installment Date", "Payment Date", "Kist Date",
    "Next Installment", "Payment Status", "Payment Update",
    "Beneficiary List", "Status Check",
    "DBT Payment", "Direct Benefit Transfer",
    "Scheme Update", "Yojana Update",
    "Women Empowerment", "Mahila Yojana", "Mahila Kalyan",
    "Women Welfare", "Girl Child Scheme", "Women Safety Scheme",
    "Women Entrepreneurship", "Women Loan Scheme",
    "Self Help Group", "SHG Loan", "NRLM Women",
    "Women Skill Development", "Women Training Program",
    "Scholarship for Girls", "Girl Education Scheme",
    "Women Helpline", "Mahila Helpline",
    "Women Pension Scheme", "Widow Pension Women",
    "Women Financial Assistance",
    "Women Portal", "Mahila Portal",
    "Kanya Vivah Yojana", "Kanya Protsahan",
    "Women Startup India", "Nari Shakti",
    "Kisan Payment", "Farmer Payment", "Farm Subsidy",
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
ALL_KEYWORDS = CENTRAL_SCHEMES + STATE_SCHEMES + GENERAL_SCHEME_KEYWORDS

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
    "kist", "kist date", "next installment", "payment date", "installment date",
]

# ── Content Ideas (installment/payment date focused) ─────────────────────────
# Every idea MUST have "installment date" or "payment date" in the topic title.
CONTENT_IDEAS = [
    # Women welfare schemes
    {"topic": "Ladli Behna Yojana 33rd Installment Date 2026", "matched_keyword": "Ladli Behna Yojana 33rd Installment Date"},
    {"topic": "Ladki Bahin Yojana 21st Installment Date Maharashtra 2026", "matched_keyword": "Ladki Bahin Yojana 21st Installment Date"},
    {"topic": "Subhadra Yojana 6th Installment Date Odisha 2026", "matched_keyword": "Subhadra Yojana 6th Installment Date"},
    {"topic": "Mahtari Vandana Yojana 24th Installment Date Chhattisgarh", "matched_keyword": "Mahtari Vandana Yojana 24th Installment Date"},
    {"topic": "Gruha Lakshmi Yojana Next Installment Date Karnataka 2026", "matched_keyword": "Gruha Lakshmi Yojana Installment Date"},
    {"topic": "Ladli Laxmi Yojana Installment Date 2026 MP", "matched_keyword": "Ladli Laxmi Yojana Installment Date"},
    {"topic": "Kanyashree Prakalpa Payment Date 2026 West Bengal", "matched_keyword": "Kanyashree Prakalpa Payment Date"},
    {"topic": "Laxmi Bhandar Payment Date 2026 West Bengal", "matched_keyword": "Laxmi Bhandar Payment Date"},
    {"topic": "Lado Laxmi Yojana 3rd Installment Date Rajasthan 2026", "matched_keyword": "Lado Laxmi Yojana 3rd Installment Date"},
    {"topic": "PMMVY Installment Date 2026: Matru Vandana Payment Update", "matched_keyword": "PMMVY Installment Date"},
    {"topic": "Mukhyamantri Kanya Utthan Yojana Payment Date Bihar 2026", "matched_keyword": "Mukhyamantri Kanya Utthan Yojana Payment Date"},
    {"topic": "Mukhyamantri Mahila Samman Yojana Payment Date Delhi 2026", "matched_keyword": "Mukhyamantri Mahila Samman Yojana Payment Date"},
    # Farmer / Agriculture schemes
    {"topic": "PM Kisan 23rd Installment Date 2026", "matched_keyword": "PM Kisan 23rd Installment Date"},
    {"topic": "PM Kisan Next Installment Date 2026: Samman Nidhi", "matched_keyword": "PM Kisan Next Installment Date"},
    {"topic": "Rythu Bharosa Payment Date 2026 Telangana", "matched_keyword": "Rythu Bharosa Payment Date"},
    {"topic": "Rythu Bandhu Payment Date 2026 Telangana", "matched_keyword": "Rythu Bandhu Payment Date"},
    {"topic": "Namo Shetkari Yojana 9th Installment Date Maharashtra 2026", "matched_keyword": "Namo Shetkari Yojana 9th Installment Date"},
    {"topic": "Krishak Bandhu Payment Date 2026 West Bengal", "matched_keyword": "Krishak Bandhu Payment Date"},
    {"topic": "CM Kisan Kalyan Yojana Installment Date MP 2026", "matched_keyword": "CM Kisan Kalyan Yojana Installment Date"},
    {"topic": "Annadata Sukhibhava Payment Date 2026 Andhra Pradesh", "matched_keyword": "Annadata Sukhibhava Payment Date"},
    {"topic": "Kalia Yojana Installment Date 2026 Odisha", "matched_keyword": "Kalia Yojana Installment Date"},
    {"topic": "YSR Rythu Bharosa Payment Date 2026 AP", "matched_keyword": "YSR Rythu Bharosa Payment Date"},
    # Housing / Welfare
    {"topic": "PM Awas Yojana Installment Date 2026 Gramin", "matched_keyword": "PM Awas Yojana Installment Date"},
    {"topic": "PM Awas Yojana Urban Payment Date 2026", "matched_keyword": "PM Awas Yojana Urban Payment Date"},
    # Gas / Subsidy
    {"topic": "Ujjwala Yojana Subsidy Payment Date 2026", "matched_keyword": "Ujjwala Yojana Payment Date"},
    {"topic": "LPG Subsidy Payment Date 2026", "matched_keyword": "LPG Subsidy Payment Date"},
    # Financial Inclusion
    {"topic": "Jan Dhan Yojana Payment Date 2026", "matched_keyword": "Jan Dhan Yojana Payment Date"},
    {"topic": "Sukanya Samriddhi Yojana Payment Date 2026", "matched_keyword": "Sukanya Samriddhi Yojana Payment Date"},
    # Multilingual (Hindi)
    {"topic": "लाडली बहना योजना 33वीं किस्त तारीख 2026", "matched_keyword": "लाडली बहना योजना किस्त तारीख"},
    {"topic": "पीएम किसान 23वीं किस्त तारीख 2026", "matched_keyword": "पीएम किसान किस्त तारीख"},
    {"topic": "महतारी वंदन योजना किस्त तारीख 2026", "matched_keyword": "महतारी वंदन योजना किस्त"},
    {"topic": "सुभद्रा योजना 6वीं किस्त तारीख 2026", "matched_keyword": "सुभद्रा योजना किस्त तारीख"},
    # Multilingual (Marathi)
    {"topic": "लाडकी बहीण योजना 21वा हप्ता तारीख 2026", "matched_keyword": "लाडकी बहीण योजना हप्ता तारीख"},
    {"topic": "नमो शेतकरी योजना 9वा हप्ता तारीख 2026", "matched_keyword": "नमो शेतकरी योजना हप्ता"},
]

# Detection Settings
SPIKE_THRESHOLD = 2.0
SPIKE_MIN_SCORE = 25
ROLLING_WINDOW_HOURS = 24
SCAN_INTERVAL_MINUTES = 120
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
