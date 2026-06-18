import re
from datetime import date, timedelta

from notion_client import Client

from config import (
    NOTION_TOKEN,
    DB_RECRUITING, DB_SCHOOL, DB_FINANCE, DB_HEALTH,
    SEEDED_RECRUITING, SEEDED_FINANCE,
)


def _client() -> Client:
    if not NOTION_TOKEN:
        raise ValueError("NOTION_TOKEN is not set. Add it to your .env file.")
    return Client(auth=NOTION_TOKEN)


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _existing_titles(notion: Client, db_id: str, title_prop: str = "title") -> set[str]:
    """Return normalized title strings already in the database."""
    titles = set()
    cursor = None
    while True:
        kwargs = {"database_id": db_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.databases.query(**kwargs)
        for page in resp.get("results", []):
            props = page.get("properties", {})
            for prop in props.values():
                if prop.get("type") == "title":
                    for rt in prop.get("title", []):
                        titles.add(_normalize(rt.get("plain_text", "")))
                    break
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return titles


def _title(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def _rich_text(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text or ""}}]


def _select(value: str) -> dict:
    return {"select": {"name": value}}


def _date(iso: str | None) -> dict:
    return {"date": {"start": iso}} if iso else {"date": None}


_NEXT_ACTION_BY_STAGE = {
    "Applying":     "Submit application",
    "Applied":      "Await response — follow up in 2 weeks if no reply",
    "OA":           "Complete online assessment",
    "Phone Screen": "Prep for phone screen",
    "Interview":    "Prep for technical interview",
    "Offer":        "Evaluate and negotiate offer",
    "Closed":       "",
}


# ---------------------------------------------------------------------------
# Database writers
# ---------------------------------------------------------------------------

def write_recruiting(entries: list[dict], dry_run: bool = False) -> tuple[int, int]:
    notion   = _client()
    existing = _existing_titles(notion, DB_RECRUITING) | SEEDED_RECRUITING
    added = skipped = 0

    for entry in entries:
        key = _normalize(entry["company"])
        if key in existing:
            skipped += 1
            continue

        next_action = _NEXT_ACTION_BY_STAGE.get(entry["stage"], "")

        if dry_run:
            print(f"  [DRY RUN] Recruiting: {entry['company']} — {entry['role']} ({entry['stage']})")
            added += 1
            existing.add(key)
            continue

        notion.pages.create(
            parent={"database_id": DB_RECRUITING},
            properties={
                "Company":      {"title": _title(entry["company"])},
                "Role":         {"rich_text": _rich_text(entry["role"])},
                "Stage":        _select(entry["stage"]),
                "Deadline":     _date(entry.get("deadline")),
                "Next Action":  {"rich_text": _rich_text(next_action)},
                "Last Contact": _date(entry.get("last_contact")),
                "Notes":        {"rich_text": _rich_text(entry.get("notes", ""))},
            },
        )
        added += 1
        existing.add(key)

    return added, skipped


def write_finance(entries: list[dict], dry_run: bool = False) -> tuple[int, int]:
    notion   = _client()
    existing = _existing_titles(notion, DB_FINANCE) | SEEDED_FINANCE
    added = skipped = 0

    for entry in entries:
        key = _normalize(entry["item"])
        if key in existing:
            skipped += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] Finance: {entry['item']} ({entry['type']})")
            added += 1
            existing.add(key)
            continue

        notion.pages.create(
            parent={"database_id": DB_FINANCE},
            properties={
                "Item":     {"title": _title(entry["item"])},
                "Type":     _select(entry["type"]),
                "Amount":   {"rich_text": _rich_text(entry.get("amount", ""))},
                "Due Date": _date(entry.get("due_date")),
                "Status":   _select("Pending"),
                "Notes":    {"rich_text": _rich_text(entry.get("notes", ""))},
            },
        )
        added += 1
        existing.add(key)

    return added, skipped


def write_school(entries: list[dict], dry_run: bool = False) -> tuple[int, int]:
    notion   = _client()
    existing = _existing_titles(notion, DB_SCHOOL)
    added = skipped = 0

    for entry in entries:
        key = _normalize(entry["assignment"])
        if key in existing:
            skipped += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] School: {entry['assignment']} ({entry['course']})")
            added += 1
            existing.add(key)
            continue

        notion.pages.create(
            parent={"database_id": DB_SCHOOL},
            properties={
                "Assignment": {"title": _title(entry["assignment"])},
                "Course":     {"rich_text": _rich_text(entry.get("course", ""))},
                "Status":     _select("Not Started"),
                "Due Date":   _date(entry.get("due_date")),
                "Notes":      {"rich_text": _rich_text(entry.get("notes", ""))},
            },
        )
        added += 1
        existing.add(key)

    return added, skipped


def write_health_backfill(dry_run: bool = False) -> tuple[int, int]:
    """Add one Health Log row per day for the past 7 days (skips existing)."""
    notion   = _client()
    existing = _existing_titles(notion, DB_HEALTH)
    added = skipped = 0

    today = date.today()
    for offset in range(7):
        target = today - timedelta(days=offset)
        label  = target.strftime("%A, %B %d").replace(" 0", " ")  # "Saturday, June 06" → "Saturday, June 6"

        if _normalize(label) in existing:
            skipped += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] Health: {label}")
            added += 1
            continue

        notion.pages.create(
            parent={"database_id": DB_HEALTH},
            properties={
                "Date": {"title": _title(label)},
                # Leave Worked Out, Workout Type, Ate Well blank — user fills in
            },
        )
        added += 1

    return added, skipped
