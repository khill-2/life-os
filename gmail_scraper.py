import base64
import re
from email.utils import parsedate_to_datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE = Path(__file__).parent

# Account definitions: name → (credentials file, token file)
ACCOUNTS = {
    "personal": (BASE / "credentials.json",        BASE / "token_personal.json"),
    "school":   (BASE / "credentials_school.json", BASE / "token_school.json"),
}

# Migrate existing token.json → token_personal.json on first run
_old_token = BASE / "token.json"
if _old_token.exists() and not (BASE / "token_personal.json").exists():
    _old_token.rename(BASE / "token_personal.json")


def _get_service(account: str = "personal"):
    if account not in ACCOUNTS:
        raise ValueError(f"Unknown account '{account}'. Choose from: {list(ACCOUNTS)}")

    creds_path, token_path = ACCOUNTS[account]
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"{creds_path.name} not found. Download the OAuth client JSON "
                    "from Google Cloud Console and place it next to this script."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _decode_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")

    if mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _decode_body(part)
            if text:
                return text

    return ""


def _parse_message(svc, msg_stub: dict) -> dict | None:
    try:
        msg = svc.users().messages().get(
            userId="me", id=msg_stub["id"], format="full"
        ).execute()
    except Exception:
        return None

    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    subject  = headers.get("subject", "")
    sender   = headers.get("from", "")
    date_str = headers.get("date", "")

    try:
        date = parsedate_to_datetime(date_str)
    except Exception:
        date = None

    body = _decode_body(msg["payload"])

    domain_match = re.search(r"@([\w.-]+)", sender)
    domain = domain_match.group(1).lower() if domain_match else ""

    return {
        "id":      msg_stub["id"],
        "subject": subject,
        "sender":  sender,
        "domain":  domain,
        "date":    date,
        "body":    body[:4000],
        "snippet": msg.get("snippet", ""),
    }


def fetch_emails(query: str, max_results: int = 50, account: str = "personal") -> list[dict]:
    """Return parsed email dicts matching `query` from the given account."""
    svc = _get_service(account)
    results = svc.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    stubs = results.get("messages", [])
    emails = []
    for stub in stubs:
        parsed = _parse_message(svc, stub)
        if parsed:
            emails.append(parsed)
    return emails
