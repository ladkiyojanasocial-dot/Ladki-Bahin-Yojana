"""
Master registry for India women empowerment schemes and reusable coverage logic.
"""
from datetime import datetime
import re


# Central + state scheme registry used by detection, categorization, and coverage planning.
SCHEME_REGISTRY = [
    {"id": "ladli_behna", "name": "Ladli Behna Yojana", "level": "state", "state": "Madhya Pradesh", "priority": 10,
     "category_slug": "ladli-behna-yojana", "aliases": ["ladli bahan", "mukhyamantri ladli behna"]},
    {"id": "majhi_ladki_bahin", "name": "Majhi Ladki Bahin Yojana", "level": "state", "state": "Maharashtra", "priority": 10,
     "category_slug": "majhi-ladki-bahin-yojana", "aliases": ["mukhyamantri majhi ladki bahin", "ladki bahin yojana"]},
    {"id": "subhadra", "name": "Subhadra Yojana Odisha", "level": "state", "state": "Odisha", "priority": 9,
     "category_slug": "subhadra-yojana", "aliases": ["subhadra yojana", "odisha women scheme"]},
    {"id": "gruha_lakshmi", "name": "Gruha Lakshmi Yojana", "level": "state", "state": "Karnataka", "priority": 9,
     "category_slug": "gruha-lakshmi-yojana", "aliases": ["gruhalakshmi", "karnataka women scheme"]},
    {"id": "mahtari_vandan", "name": "Mahtari Vandan Yojana", "level": "state", "state": "Chhattisgarh", "priority": 8,
     "category_slug": "mahtari-vandan-yojana", "aliases": ["mahatari vandan"]},
    {"id": "kanyashree", "name": "Kanyashree Prakalpa", "level": "state", "state": "West Bengal", "priority": 8,
     "category_slug": "kanyashree-prakalpa", "aliases": ["kanyashree", "girls scholarship wb"]},
    {"id": "ladli_laxmi", "name": "Ladli Laxmi Yojana", "level": "state", "state": "Madhya Pradesh", "priority": 8,
     "category_slug": "ladli-laxmi-yojana", "aliases": ["ladli laxmi", "girl child scheme mp"]},
    {"id": "mkuy", "name": "Mukhyamantri Kanya Utthan Yojana", "level": "state", "state": "Bihar", "priority": 8,
     "category_slug": "mukhyamantri-kanya-utthan-yojana", "aliases": ["kanya utthan", "girls education bihar"]},
    {"id": "bbbp", "name": "Beti Bachao Beti Padhao", "level": "central", "state": "", "priority": 8,
     "category_slug": "beti-bachao-beti-padhao", "aliases": ["bbbp", "girl child protection scheme"]},
    {"id": "ssy", "name": "Sukanya Samriddhi Yojana", "level": "central", "state": "", "priority": 8,
     "category_slug": "sukanya-samriddhi-yojana", "aliases": ["ssy", "sukanya account"]},
    {"id": "pmmvy", "name": "Pradhan Mantri Matru Vandana Yojana", "level": "central", "state": "", "priority": 8,
     "category_slug": "pradhan-mantri-matru-vandana-yojana", "aliases": ["pmmvy", "matru vandana"]},
    {"id": "ujjwala", "name": "Ujjwala Yojana", "level": "central", "state": "", "priority": 7,
     "category_slug": "ujjwala-yojana", "aliases": ["pmuy", "pradhan mantri ujjwala yojana"]},
    {"id": "mssc", "name": "Mahila Samman Savings Certificate", "level": "central", "state": "", "priority": 7,
     "category_slug": "mahila-samman-savings-certificate", "aliases": ["mssc", "mahila samman certificate"]},
    {"id": "step", "name": "STEP Scheme", "level": "central", "state": "", "priority": 7,
     "category_slug": "step-scheme-women", "aliases": ["support to training and employment programme for women"]},
    {"id": "one_stop_centre", "name": "One Stop Centre", "level": "central", "state": "", "priority": 7,
     "category_slug": "one-stop-centre-scheme", "aliases": ["sakhi centre", "women help centre"]},
    {"id": "working_women_hostel", "name": "Working Women Hostel", "level": "central", "state": "", "priority": 6,
     "category_slug": "working-women-hostel-scheme", "aliases": ["women hostel scheme"]},
    {"id": "lakhpati_didi", "name": "Lakhpati Didi", "level": "central", "state": "", "priority": 6,
     "category_slug": "lakhpati-didi-scheme", "aliases": ["shg lakhpati didi", "women shg income scheme"]},
    {"id": "namo_drone_didi", "name": "Namo Drone Didi", "level": "central", "state": "", "priority": 6,
     "category_slug": "namo-drone-didi-scheme", "aliases": ["drone didi", "women drone scheme"]},
]

DEFAULT_ANGLES = [
    "installment_update",
    "status_check",
    "ekyc_update",
    "eligibility",
    "apply_process",
    "documents_required",
    "rejection_fixes",
    "latest_news",
]

ANGLE_TOPIC_TEMPLATES = {
    "installment_update": "{name} latest installment update {year}: date, amount, status",
    "status_check": "{name} status check {year}: payment, beneficiary and pending status",
    "ekyc_update": "{name} eKYC update {year}: deadline, process, common errors",
    "eligibility": "{name} eligibility criteria {year}: who can apply and who cannot",
    "apply_process": "{name} online apply process {year}: step-by-step guide",
    "documents_required": "{name} required documents {year}: complete checklist",
    "rejection_fixes": "{name} rejected or payment failed: reasons and how to fix",
    "latest_news": "{name} latest news update {year}: official announcements and changes",
}

ANGLE_PATTERNS = [
    ("installment_update", [r"\binstallment\b", r"\bkist\b", r"\bpayment\b"]),
    ("status_check", [r"\bstatus\b", r"\bbeneficiary\b", r"\bcheck\b"]),
    ("ekyc_update", [r"\bekyc\b", r"\be-kyc\b", r"\baadhaar\b"]),
    ("eligibility", [r"\beligib", r"\bwho can apply\b"]),
    ("apply_process", [r"\bhow to apply\b", r"\bregistration\b", r"\bapply online\b"]),
    ("documents_required", [r"\bdocument", r"\brequired papers\b"]),
    ("rejection_fixes", [r"\breject", r"\bfailed\b", r"\berror\b"]),
]


def get_registry():
    return list(SCHEME_REGISTRY)


def get_trends_keywords(limit=40):
    rows = sorted(SCHEME_REGISTRY, key=lambda x: x.get("priority", 0), reverse=True)
    out = []
    for row in rows:
        out.append(row["name"])
        out.extend(row.get("aliases", []))
    dedup = []
    seen = set()
    for kw in out:
        k = kw.strip()
        if not k:
            continue
        key = k.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(k)
        if len(dedup) >= limit:
            break
    return dedup


def build_watchlist_keywords():
    return get_trends_keywords(limit=200)


def find_best_scheme(text):
    blob = (text or "").lower()
    best = None
    best_score = -1
    for scheme in SCHEME_REGISTRY:
        score = 0
        for phrase in [scheme["name"]] + scheme.get("aliases", []):
            p = phrase.lower().strip()
            if p and p in blob:
                score += max(2, len(p.split()))
        if score > best_score:
            best = scheme
            best_score = score
    return best if best_score > 0 else None


def infer_content_angle(text):
    blob = (text or "").lower()
    for angle, patterns in ANGLE_PATTERNS:
        for pat in patterns:
            if re.search(pat, blob):
                return angle
    return "latest_news"


def get_category_slug_for_text(topic_title, matched_keyword=""):
    scheme = find_best_scheme(f"{topic_title or ''} {matched_keyword or ''}")
    if scheme:
        return scheme.get("category_slug", "news")
    return "news"


def build_angle_topic(scheme, angle, year=None):
    year = year or datetime.utcnow().year
    tmpl = ANGLE_TOPIC_TEMPLATES.get(angle, ANGLE_TOPIC_TEMPLATES["latest_news"])
    return tmpl.format(name=scheme["name"], year=year)
