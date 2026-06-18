#!/usr/bin/env python3
"""
Local JSON data layer — replaces Notion writes for recruiting, school, and health.
All data lives in data/*.json. Safe to re-run (deduplicates before writing).
"""

import json
import os
import uuid
from datetime import date, timedelta

DATA_DIR = "data"

_NEXT_ACTION = {
    "Applying":     "Submit application",
    "Applied":      "Await response — follow up in 2 weeks if no reply",
    "OA":           "Complete online assessment",
    "Phone Screen": "Prep for phone screen",
    "Interview":    "Prep for technical interview",
    "Offer":        "Evaluate and negotiate offer",
    "Closed":       "",
}


def _load(filename: str) -> list:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f).get("entries", [])


def _save(filename: str, entries: list) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump({"entries": entries}, f, indent=2)


def write_recruiting(entries: list[dict], dry_run: bool = False) -> tuple[int, int]:
    existing      = _load("recruiting.json")
    existing_keys = {e["company"].lower().strip() for e in existing}
    added = skipped = 0

    for entry in entries:
        key = entry["company"].lower().strip()
        if key in existing_keys:
            skipped += 1
            continue
        if dry_run:
            print(f"  [DRY RUN] Recruiting: {entry['company']} — {entry['role']} ({entry['stage']})")
            added += 1
            existing_keys.add(key)
            continue
        existing.append({
            "id":           str(uuid.uuid4()),
            "company":      entry["company"],
            "role":         entry.get("role", "Software Engineering Intern"),
            "stage":        entry.get("stage", "Applied"),
            "deadline":     entry.get("deadline"),
            "next_action":  _NEXT_ACTION.get(entry.get("stage", "Applied"), ""),
            "last_contact": entry.get("last_contact"),
            "notes":        entry.get("notes", ""),
            "created_at":   date.today().isoformat(),
        })
        existing_keys.add(key)
        added += 1

    if not dry_run:
        _save("recruiting.json", existing)
    return added, skipped


def write_school(entries: list[dict], dry_run: bool = False) -> tuple[int, int]:
    existing      = _load("school.json")
    existing_keys = {e["assignment"].lower().strip() for e in existing}
    added = skipped = 0

    for entry in entries:
        key = entry["assignment"].lower().strip()
        if key in existing_keys:
            skipped += 1
            continue
        if dry_run:
            print(f"  [DRY RUN] School: {entry['assignment']} ({entry.get('course', '')})")
            added += 1
            existing_keys.add(key)
            continue
        existing.append({
            "id":         str(uuid.uuid4()),
            "assignment": entry["assignment"],
            "course":     entry.get("course", ""),
            "status":     "Not Started",
            "due_date":   entry.get("due_date"),
            "notes":      entry.get("notes", ""),
            "created_at": date.today().isoformat(),
        })
        existing_keys.add(key)
        added += 1

    if not dry_run:
        _save("school.json", existing)
    return added, skipped


def write_health_backfill(dry_run: bool = False) -> tuple[int, int]:
    existing       = _load("health.json")
    existing_dates = {e["date"] for e in existing}
    added = skipped = 0

    today = date.today()
    for offset in range(14):
        target = today - timedelta(days=offset)
        iso = target.isoformat()
        if iso in existing_dates:
            skipped += 1
            continue
        if dry_run:
            print(f"  [DRY RUN] Health: {iso}")
            added += 1
            continue
        existing.append({
            "id":           str(uuid.uuid4()),
            "date":         iso,
            "worked_out":   False,
            "workout_type": "",
            "ate_well":     False,
            "notes":        "",
        })
        existing_dates.add(iso)
        added += 1

    if not dry_run:
        existing.sort(key=lambda e: e["date"], reverse=True)
        _save("health.json", existing)
    return added, skipped
