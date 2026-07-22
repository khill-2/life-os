import re
from datetime import date, datetime
from typing import Optional

from config import STAGE_KEYWORDS, TARGET_COMPANIES, FINANCE_DOMAINS

# Domains/roots that should never be treated as a recruiting company
_RECRUITING_BLOCKLIST = {
    "gmail", "googlemail", "yahoo", "outlook", "hotmail", "icloud",   # mail services
    "linkedin", "indeed", "glassdoor", "ziprecruiter", "greenhouse",
    "icims", "workday", "taleo", "smartrecruiters", "jobvite",         # ATS platforms (direct)
    "leetcode", "hackerrank", "codesignal", "codility", "algo",        # coding platforms
    "levels", "teamblind", "blind",                                     # job discussion sites
    "martinizing", "beckettsimonon", "shipsticks", "capitaloneshopping",
    "newyorktimes", "nytimes", "garmin", "logitech",                   # non-tech consumer brands
    "notion",                                                           # product emails, not recruiting
}

# ATS platform domain roots — sender is the ATS, not the company.
# Company must be extracted from subject/sender name instead.
# If extraction fails, _extract_company returns None (not the ATS platform name).
_ATS_ROOTS = {"greenhouse-mail", "myworkday", "ashbyhq", "lever"}

# Extra domain-level suffixes that are also ATS (matched against full domain, not just root)
_ATS_DOMAIN_CONTAINS = {"greenhouse-mail", "myworkday", "ashbyhq"}

_ATS_JUNK_LOCALS = {"workday", "hr", "noreply", "no-reply", "donotreply", "jj", "mailbox"}

_ATS_SUBJECT_PATTERNS = [
    # "Thank you for applying to Anduril Industries, Keller!"
    re.compile(r"(?:applying|applied) to ([A-Z][A-Za-z\s&,\-]+?)(?:,\s*\w+)?[!.]?\s*$", re.IGNORECASE),
    # "Lyft Update - Software Engineer Intern..."
    re.compile(r"^([A-Z][A-Za-z]+)\s+(?:Update|Application|Status|Opportunity)\b"),
    # "Thank you for your interest in Tesla" / "Thanks for your interest in Hermeus"
    re.compile(r"(?:interest in|joining) ([A-Z][A-Za-z\s&]+?)(?:,|!|\.|\s*$)"),
    # "GEICO Application Status"
    re.compile(r"^([A-Z]{2,}[A-Za-z]*)\s+(?:Application|Update|Status)\b"),
    # "Ramp | Software Engineer"  or "Let's stay in touch | Ramp"
    re.compile(r"\|\s*([A-Z][A-Za-z]+)\s*$"),
    re.compile(r"^([A-Z][A-Za-z]+)\s*\|"),
]

_ATS_REJECT_WORDS = {"workday", "greenhouse", "lever", "ashby", "update", "status", "new"}


def _extract_ats_company(domain: str, sender: str, subject: str) -> Optional[str]:
    """For ATS platform senders, extract the actual company name. Returns None if unknown."""
    root = domain.split(".")[-2] if domain.count(".") >= 1 else domain
    if root not in _ATS_ROOTS:
        return None

    # Workday: local part of address encodes the company (e.g. nvidia@myworkday.com)
    if root == "myworkday":
        m = re.search(r"([^@<\s]+)@myworkday\.com", sender)
        if m:
            local = m.group(1).lower().split(".")[-1]  # handle "Mailbox.CIBC-..." → "cibc-..."
            # Strip trailing junk suffixes added by some Workday configs
            local = re.sub(r"-?workday.*$", "", local).strip("-")
            if local and local not in _ATS_JUNK_LOCALS and len(local) >= 2:
                clean = local.replace("-", " ").replace("_", " ")
                key = clean.replace(" ", "").lower()
                return _COMPANY_OVERRIDES.get(key, clean.title())

    # Try subject patterns
    for pat in _ATS_SUBJECT_PATTERNS:
        m = pat.search(subject)
        if m:
            company = m.group(1).strip().rstrip(",.")
            if company.lower() in _ATS_REJECT_WORDS:
                continue
            key = company.lower().replace(" ", "").replace("-", "")
            return _COMPANY_OVERRIDES.get(key, company.title())

    return None

_PROMO_SIGNALS = [
    "% off", "sale", "deal", "discount", "coupon", "offer from",
    "daily digest", "workday inbox",
    "save up to", "limited time", "free shipping", "shop now",
    "unsubscribe", "new styles", "new arrivals", "gift subscription",
    "streaming day", "summer break", "school's out",
    # LinkedIn / network outreach
    "i want to connect", "i'd like to connect", "let's connect",
    "wants to connect with you", "sent you a connection request",
    "invitation to connect", "join my professional network",
    "would love to connect", "hope to connect", "selective outreach",
    # Product / brand noise
    "new golf", "father-son", "collegiate polo",
    # Finance promos (not real transactions)
    "could get paid sooner", "set up direct deposit", "get paid faster",
    "open a savings", "earn more with", "refer a friend",
]

# Patterns that flag generic outreach — checked against subject AND snippet
_GENERIC_OUTREACH = re.compile(
    r"(i want to connect|i'?d like to connect|let'?s connect|quick question|"
    r"following up|checking in|touching base|re: availability|"
    r"wants to connect|invitation to connect|connection request|"
    r"open to connecting|open to new opportunities|happy to connect|"
    r"reach out to you|reaching out to you|hope this finds you)",
    re.IGNORECASE,
)


def _is_generic_outreach(subject: str, snippet: str = "") -> bool:
    return bool(_GENERIC_OUTREACH.search(subject) or _GENERIC_OUTREACH.search(snippet))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _is_promo(subject: str) -> bool:
    s = subject.lower()
    return any(p in s for p in _PROMO_SIGNALS)


_COMPANY_OVERRIDES = {
    "amazon": "Amazon",
    "google": "Google",
    "meta": "Meta",
    "apple": "Apple",
    "microsoft": "Microsoft",
    "netflix": "Netflix",
    "nvidia": "NVIDIA",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "stripe": "Stripe",
    "databricks": "Databricks",
    "roblox": "Roblox",
    "robinhood": "Robinhood",
    "tiktok": "TikTok",
    "zoom": "Zoom",
    "rivian": "Rivian",
    "spacex": "SpaceX",
    "activision": "Activision",
    "hpe": "HPE",
    "oraclecloud": "Oracle",
    "capitalone": "Capital One",
    "twilio": "Twilio",
    "palantir": "Palantir",
    "uber": "Uber",
    "lyft": "Lyft",
    "airbnb": "Airbnb",
    "coinbase": "Coinbase",
    "salesforce": "Salesforce",
    "linkedin": "LinkedIn",
    "twitter": "Twitter",
    "snap": "Snap",
    "pinterest": "Pinterest",
    "doordash": "DoorDash",
    "instacart": "Instacart",
    "waymo": "Waymo",
    "tesla": "Tesla",
    "cloudflare": "Cloudflare",
    "anduril": "Anduril",
    "andurilindustries": "Anduril",
    "ramp": "Ramp",
    "imc": "IMC",
    "geico": "GEICO",
    "tmobile": "T-Mobile",
    "intel": "Intel",
    "hermeus": "Hermeus",
    "lowes": "Lowe's",
    "boeing": "Boeing",
    "gemini": "Gemini",
    "invesco": "Invesco",
}


def _extract_company(email: dict) -> Optional[str]:
    domain  = email.get("domain", "")
    sender  = email.get("sender", "")
    subject = email.get("subject", "")
    root    = domain.split(".")[-2] if domain.count(".") >= 1 else domain

    # ATS platform senders: must extract company from subject/sender; never use the ATS name
    if root in _ATS_ROOTS:
        return _extract_ats_company(domain, sender, subject)

    if domain in FINANCE_DOMAINS or root in _RECRUITING_BLOCKLIST:
        return None

    return _COMPANY_OVERRIDES.get(root, root.capitalize()) if root else None


def _infer_stage(text: str) -> str:
    lower = text.lower()
    for stage, keywords in STAGE_KEYWORDS:
        if not keywords:
            return stage
        if any(kw in lower for kw in keywords):
            return stage
    return "Applied"


def _extract_date(text: str, fallback: Optional[datetime] = None) -> Optional[str]:
    patterns = [
        r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),?\s+(\d{4})\b",
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|"
        r"November|December)\s+(\d{4})\b",
    ]
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        try:
            raw = m.group(0)
            for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(raw, fmt).date().isoformat()
                except ValueError:
                    pass
            parts = re.split(r"[\s,]+", raw)
            if len(parts) == 3:
                try:
                    if parts[0].lower() in months:
                        return date(int(parts[2]), months[parts[0].lower()], int(parts[1])).isoformat()
                    if parts[1].lower() in months:
                        return date(int(parts[2]), months[parts[1].lower()], int(parts[0])).isoformat()
                except (ValueError, KeyError):
                    pass
        except Exception:
            continue

    return fallback.date().isoformat() if fallback else None


def _extract_role(subject: str, body: str) -> str:
    """Extract role from subject first (highest signal), then body."""
    # Subject patterns like "Amazon Virtual Interview | SDE Intern (Fall)"
    subject_patterns = [
        r"\|\s*([^|]{5,60}(?:intern|engineer|developer|scientist|analyst)[^|]{0,30})",
        r"[-–]\s*([A-Za-z][^-]{5,60}(?:intern|engineer|developer|scientist|analyst)[^-]{0,30})",
        r"(?:position|role|opening):\s*([A-Za-z][^\n,]{5,60})",
    ]
    for pattern in subject_patterns:
        m = re.search(pattern, subject, re.IGNORECASE)
        if m:
            role = m.group(1).strip().rstrip(".")
            if len(role) < 80 and role and role[0].isupper() and len(role.split()) >= 2:
                return role

    # Fall back to body — stricter to avoid sentence fragments
    body_patterns = [
        r"(?:position|role|opening|opportunity)\s*[:\-]?\s*([A-Z][^\n,.]{3,60})",
        r"([A-Z][^\n,]*?(?:Intern|Engineer|Developer|Analyst|Scientist)[^\n,]{0,25})",
    ]
    for pattern in body_patterns:
        m = re.search(pattern, body)  # no IGNORECASE — require uppercase start
        if m:
            role = m.group(1).strip()
            if len(role) < 70 and "." not in role and 2 <= len(role.split()) <= 8:
                return role
    return ""


def _extract_amount(text: str) -> str:
    m = re.search(r"\$[\d,]+(?:\.\d{2})?", text)
    return m.group(0) if m else ""


def _finance_type(subject: str, body: str, domain: str) -> str:
    combined = (subject + " " + body).lower()
    if any(w in combined for w in ["investment", "brokerage", "stock", "portfolio", "robinhood"]):
        return "Investment"
    if any(w in combined for w in ["transfer", "wire", "deposit", "zelle"]):
        return "Transfer"
    if any(w in combined for w in ["bill", "invoice", "due", "payment"]):
        return "Bill"
    if any(w in combined for w in ["savings", "save"]):
        return "Savings"
    return "One-Time"


# ---------------------------------------------------------------------------
# Public classifiers
# ---------------------------------------------------------------------------

def classify_recruiting(email: dict) -> Optional[dict]:
    subject  = email.get("subject", "")
    snippet  = email.get("snippet", "")
    combined = (subject + " " + email["body"] + " " + snippet).lower()
    domain   = email.get("domain", "")
    root     = domain.split(".")[-2] if domain.count(".") >= 1 else domain

    is_ats = root in _ATS_ROOTS
    if not is_ats:
        if domain in FINANCE_DOMAINS or root in _RECRUITING_BLOCKLIST:
            return None
    if _is_promo(subject) or _is_generic_outreach(subject, snippet):
        return None

    subject_lower = subject.lower()

    # Actionable = email signals a real recruiting step (interview, OA, offer, confirmed application)
    actionable_keywords = [
        "interview", "online assessment", "coding challenge", "offer letter",
        "virtual interview", "technical screen", "application received",
        "thank you for applying", "thanks for applying", "next steps", "take-home",
        "thank you for your interest", "thanks for your interest",
        "application update", "application status", "we received your application",
    ]
    # Awareness = mentions a role/program but could be cold outreach
    awareness_keywords = [
        "internship", "intern", "sde intern", "your application",
        "software engineer intern", "new grad", "we received your resume",
    ]

    from_target     = root.lower() in TARGET_COMPANIES or is_ats
    snippet_lower   = snippet.lower()
    has_actionable  = any(kw in subject_lower or kw in snippet_lower for kw in actionable_keywords)
    has_awareness   = any(kw in subject_lower or kw in snippet_lower for kw in awareness_keywords)

    # Target companies + ATS-sent emails: awareness signal is enough
    # Unknown sender: must have an actionable signal
    if from_target:
        if not (has_actionable or has_awareness):
            return None
    else:
        if not has_actionable:
            return None

    company = _extract_company(email)
    if not company:
        return None

    role      = _extract_role(subject, email["body"])
    stage     = _infer_stage(combined)
    last_date = email["date"].date().isoformat() if email.get("date") else None
    deadline  = _extract_date(email["body"])

    return {
        "company":      company,
        "role":         role or "Software Engineering Intern",
        "stage":        stage,
        "deadline":     deadline,
        "last_contact": last_date,
        "notes":        email["snippet"][:200],
    }


def classify_finance(email: dict) -> Optional[dict]:
    subject  = email.get("subject", "")
    snippet  = email.get("snippet", "")
    combined = (subject + " " + email["body"] + " " + snippet).lower()
    domain   = email.get("domain", "")

    if _is_promo(subject) or _is_generic_outreach(subject, snippet):
        return None

    transactional_keywords = [
        "paycheck", "direct deposit", "statement ready", "bill due", "payment due",
        "invoice", "subscription renewal", "transfer complete", "transfer received",
        "your transfer", "payment confirmed", "payment confirmation",
        "debit card", "card declined", "bank account", "withdrawal", "deposit",
        "balance update", "directpay", "autopay",
    ]
    from_finance_domain = domain in FINANCE_DOMAINS
    has_transactional   = any(kw in combined for kw in transactional_keywords)

    if not (from_finance_domain or has_transactional):
        return None

    friendly = FINANCE_DOMAINS.get(domain)
    item     = friendly or email["subject"][:80] or "Finance item"
    amount   = _extract_amount(email["body"] + " " + email["subject"])
    due_date = _extract_date(combined, email.get("date"))
    ftype    = _finance_type(subject, email["body"], domain)

    return {
        "item":     item,
        "type":     ftype,
        "amount":   amount,
        "due_date": due_date,
        "notes":    email["snippet"][:200],
    }


def classify_school(email: dict) -> Optional[dict]:
    subject  = email.get("subject", "")
    snippet  = email.get("snippet", "")
    combined = (subject + " " + email["body"] + " " + snippet).lower()
    domain   = email.get("domain", "")

    if _is_promo(subject) or _is_generic_outreach(subject, snippet):
        return None

    # Must come from a school/university domain for weak matches to count
    from_school = domain.endswith(".edu") or "umich.edu" in domain

    # Strong signals: any one is sufficient regardless of sender
    strong_keywords = [
        "assignment due", "project due", "gradescope", "quiz due",
        "homework due", "hw due", "exam reminder", "submission deadline",
        "canvas notification", "eecs 4", "eecs 3", "eecs 2",
        "grade posted", "your grade", "office hours", "lecture recording",
    ]
    # Weak signals: require 3+ AND must be from a school domain
    weak_keywords = [
        "syllabus", "eecs", "university of michigan", "umich",
        "assignment", "exam", "quiz", "homework", " hw ", "submission",
        "gradebook", "lecture", "lab section", "course syllabus",
    ]

    has_strong = any(kw in combined for kw in strong_keywords)
    weak_count = sum(1 for kw in weak_keywords if kw in combined)

    # Require subject to contain at least one academic word for weak matches
    subject_academic = any(w in subject.lower() for w in [
        "eecs", "assignment", "exam", "quiz", "homework", "hw", "course",
        "grade", "gradescope", "canvas", "lecture", "lab", "project", "due",
    ])

    if not (has_strong or (weak_count >= 3 and subject_academic and from_school)):
        return None

    course = ""
    m = re.search(
        r"(EECS\s*\d{3}|(?:EECS|ROB|MECHENG|ECE|MATH|PHYSICS)\s*\d+\w*)",
        subject + " " + email["body"], re.IGNORECASE,
    )
    if m:
        course = m.group(0).upper()

    assignment = subject[:120] if subject else "Assignment"
    due_date   = _extract_date(combined, email.get("date"))

    return {
        "assignment": assignment,
        "course":     course,
        "due_date":   due_date,
        "notes":      email["snippet"][:200],
    }
