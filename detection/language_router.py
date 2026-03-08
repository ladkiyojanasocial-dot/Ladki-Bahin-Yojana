"""
Language router for English/Hindi/Telugu content generation.
"""
import re

SUPPORTED_LANGS = {"en", "hi", "te"}

# Unicode ranges
_RE_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_RE_TELUGU = re.compile(r"[\u0C00-\u0C7F]")

# Light keyword hints when script is Latin but query is Hindi/Telugu intent.
HI_HINTS = (
    "yojana", "kisan", "kisaan", "yojna", "aavedan", "patrata", "status", "kist", "bhugtan"
)
TE_HINTS = (
    "raithu", "rythu", "panta", "chasa", "telangana", "andhra", "labharthi"
)


def normalize_lang(lang):
    l = (lang or "").strip().lower()
    return l if l in SUPPORTED_LANGS else "en"


def detect_language_from_text(text):
    blob = text or ""
    if _RE_TELUGU.search(blob):
        return "te"
    if _RE_DEVANAGARI.search(blob):
        return "hi"

    low = blob.lower()
    hi_score = sum(1 for h in HI_HINTS if h in low)
    te_score = sum(1 for h in TE_HINTS if h in low)
    if te_score >= 2 and te_score > hi_score:
        return "te"
    if hi_score >= 2:
        return "hi"
    return "en"


def detect_topic_language(topic_title, stories=None, matched_keyword=""):
    score = {"en": 0, "hi": 0, "te": 0}

    def _bump(lang, pts):
        score[lang] = score.get(lang, 0) + pts

    seed_texts = [topic_title or "", matched_keyword or ""]
    for txt in seed_texts:
        _bump(detect_language_from_text(txt), 2)

    for s in (stories or [])[:6]:
        text = f"{s.get('title', '')} {s.get('summary', '')}"
        _bump(detect_language_from_text(text), 1)

    # English remains safe fallback on ties.
    best = max(score.items(), key=lambda x: x[1])[0]
    if score.get(best, 0) <= 0:
        return "en"
    return normalize_lang(best)
