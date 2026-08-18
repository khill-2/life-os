import re as _re

# Gmail search queries per category
GMAIL_QUERIES = {
    "recruiting": (
        'category:primary (internship OR interview OR "online assessment" OR '
        '"coding challenge" OR "thank you for applying" OR "thanks for your interest" OR '
        '"thanks for applying" OR "we received your application" OR "we received your resume" OR '
        '"next steps" OR "offer letter" OR recruiter OR "phone screen")'
    ),
    "finance": (
        "paycheck OR \"direct deposit\" OR statement OR \"bill due\" OR "
        '"payment due" OR invoice OR subscription OR renewal OR transfer OR '
        "Venmo OR Robinhood OR brokerage OR bank"
    ),
    "school": (
        '"assignment due" OR "project due" OR exam OR deadline OR submission OR '
        "Canvas OR Gradescope OR syllabus OR course OR university"
    ),
}

# Max emails to fetch per query (keeps runtime bounded)
MAX_RESULTS_PER_QUERY = 200

# Recruiting stage inference keywords (checked in order — first match wins)
STAGE_KEYWORDS = [
    ("Offer",        ["offer letter", "offer extended", "we'd like to offer", "pleased to offer"]),
    ("Interview",    ["interview", "chat with the team", "meet the team", "on-site", "technical round"]),
    ("OA",           ["coding challenge", "online assessment", "hackerrank", "codesignal", "take-home", "technical screen"]),
    ("Phone Screen", ["phone screen", "phone call", "quick call", "intro call", "recruiter call"]),
    ("Applied",      []),  # default
]

# Companies the user is actively targeting (used for context-aware classification)
# Customize this list to match the companies you're applying to
TARGET_COMPANIES = {
    "google", "meta", "apple", "microsoft", "amazon",
    "stripe", "figma", "notion", "openai", "anthropic",
}

# Finance sender domains → friendly names
# Add your own bank/brokerage domains here
FINANCE_DOMAINS = {
    "venmo.com": "Venmo",
    "paypal.com": "PayPal",
    "chase.com": "Chase",
    "bankofamerica.com": "Bank of America",
    "wellsfargo.com": "Wells Fargo",
    "robinhood.com": "Robinhood",
    "schwab.com": "Schwab",
}
