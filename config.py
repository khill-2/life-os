from dotenv import load_dotenv
import os

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")

# Database IDs (from Notion URLs)
DB_RECRUITING  = "58e58f54-eb83-43ab-85f4-54b4d76071dd"
DB_SCHOOL      = "123cdb23-81a2-48e1-8a29-6c86233dd8b6"
DB_FINANCE     = "d5633f55-03a9-47a6-8c7d-18af61c9c689"
DB_HEALTH      = "a3c1a3cc-b9fd-45d6-ab8d-6b05408ca461"

# Entries already in Notion — skip these during deduplication
SEEDED_RECRUITING = {"amazon", "spacex", "microsoft", "hpe", "notion"}
SEEDED_FINANCE    = {"brokerage transfer", "monthly budget check"}

# Gmail search queries per category
GMAIL_QUERIES = {
    "recruiting": (
        "internship OR interview OR application OR offer OR OA OR "
        '"online assessment" OR hiring OR recruiter OR "thank you for applying" OR '
        '"next steps" OR "coding challenge"'
    ),
    "finance": (
        "paycheck OR \"direct deposit\" OR statement OR \"bill due\" OR "
        '"payment due" OR invoice OR subscription OR renewal OR transfer OR '
        "Venmo OR Robinhood OR brokerage OR bank"
    ),
    "school": (
        '"assignment due" OR "project due" OR exam OR deadline OR submission OR '
        "Canvas OR Gradescope OR syllabus OR EECS OR course OR university OR Michigan"
    ),
}

# Max emails to fetch per query (keeps runtime bounded)
MAX_RESULTS_PER_QUERY = 50

# Recruiting stage inference keywords (checked in order — first match wins)
STAGE_KEYWORDS = [
    ("Offer",        ["offer letter", "offer extended", "we'd like to offer", "pleased to offer"]),
    ("Interview",    ["interview", "chat with the team", "meet the team", "on-site", "technical round"]),
    ("OA",           ["coding challenge", "online assessment", "hackerrank", "codesignal", "take-home", "technical screen"]),
    ("Phone Screen", ["phone screen", "phone call", "quick call", "intro call", "recruiter call"]),
    ("Applied",      []),  # default
]

# Companies the user is actively targeting (used for context-aware classification)
TARGET_COMPANIES = {
    "amazon", "spacex", "databricks", "roblox", "robinhood", "tiktok", "zoom",
    "google", "meta", "apple", "microsoft", "netflix", "nvidia", "openai",
    "anthropic", "stripe", "figma", "notion", "rivian",
}

# Finance sender domains → friendly names
FINANCE_DOMAINS = {
    "robinhood.com": "Robinhood",
    "usaa.com": "USAA",
    "venmo.com": "Venmo",
    "paypal.com": "PayPal",
    "chase.com": "Chase",
    "bankofamerica.com": "Bank of America",
    "wellsfargo.com": "Wells Fargo",
}
