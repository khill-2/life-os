#!/usr/bin/env python3
"""
Show the classifier in action: what passes, what's blocked and why.
Usage: python debug_classifier.py [--since DAYS] [--category recruiting|finance|school]
"""

import argparse
from config import GMAIL_QUERIES, MAX_RESULTS_PER_QUERY
from gmail_scraper import fetch_emails, ACCOUNTS
from classifier import (
    classify_recruiting, classify_finance, classify_school,
    _is_promo, _is_generic_outreach, _RECRUITING_BLOCKLIST, FINANCE_DOMAINS,
)

CYAN  = "\033[96m"
GREEN = "\033[92m"
RED   = "\033[91m"
GRAY  = "\033[90m"
BOLD  = "\033[1m"
RESET = "\033[0m"


def _root(domain):
    return domain.split(".")[-2] if domain.count(".") >= 1 else domain


def _block_reason_recruiting(email):
    subject = email.get("subject", "")
    snippet = email.get("snippet", "")
    domain  = email.get("domain", "")
    root    = _root(domain)

    if root in _RECRUITING_BLOCKLIST:
        return f"domain blocklist ({root})"
    if domain in FINANCE_DOMAINS:
        return "finance domain"
    if _is_promo(subject):
        return "promo signal in subject"
    if _is_generic_outreach(subject, snippet):
        return "generic outreach (subject or snippet)"

    subject_lower = subject.lower()
    actionable_keywords = [
        "interview", "online assessment", "coding challenge", "offer letter",
        "virtual interview", "technical screen", "application received",
        "thank you for applying", "next steps", "take-home",
    ]
    awareness_keywords = [
        "internship", "intern", "sde intern", "your application",
        "software engineer intern", "new grad",
    ]
    from config import TARGET_COMPANIES
    from_target    = root.lower() in TARGET_COMPANIES
    has_actionable = any(kw in subject_lower for kw in actionable_keywords)
    has_awareness  = any(kw in subject_lower for kw in awareness_keywords)

    if from_target and not (has_actionable or has_awareness):
        return "target company but no role/action keyword in subject"
    if not from_target and not has_actionable:
        return "unknown company — no actionable keyword in subject"
    return None  # would pass keyword check; blocked later by missing company


def _block_reason_school(email):
    subject = email.get("subject", "")
    snippet = email.get("snippet", "")
    domain  = email.get("domain", "")

    if _is_promo(subject):
        return "promo signal in subject"
    if _is_generic_outreach(subject, snippet):
        return "generic outreach"

    combined = (subject + " " + email["body"] + " " + snippet).lower()
    from_school = domain.endswith(".edu") or "umich.edu" in domain

    strong_keywords = [
        "assignment due", "project due", "gradescope", "quiz due",
        "homework due", "hw due", "exam reminder", "submission deadline",
        "canvas notification", "eecs 4", "eecs 3", "eecs 2",
        "grade posted", "your grade", "office hours", "lecture recording",
    ]
    weak_keywords = [
        "syllabus", "eecs", "university of michigan", "umich",
        "assignment", "exam", "quiz", "homework", " hw ", "submission",
        "gradebook", "lecture", "lab section", "course syllabus",
    ]
    subject_academic = any(w in subject.lower() for w in [
        "eecs", "assignment", "exam", "quiz", "homework", "hw", "course",
        "grade", "gradescope", "canvas", "lecture", "lab", "project", "due",
    ])

    has_strong  = any(kw in combined for kw in strong_keywords)
    weak_count  = sum(1 for kw in weak_keywords if kw in combined)

    if has_strong:
        return None
    if not from_school:
        return f"non-.edu sender ({domain}) and no strong keyword"
    if weak_count < 3:
        return f"only {weak_count} weak keywords (need 3+)"
    if not subject_academic:
        return "no academic word in subject"
    return None


def show(category, emails, classify_fn, block_reason_fn=None):
    passed, blocked = [], []
    for email in emails:
        result = classify_fn(email)
        if result:
            passed.append((email, result))
        else:
            reason = block_reason_fn(email) if block_reason_fn else "filtered"
            blocked.append((email, reason))

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}{category.upper()} — {len(passed)} passed, {len(blocked)} blocked{RESET}")

    if passed:
        print(f"\n{GREEN}{BOLD}✅ WOULD BE ADDED TO NOTION:{RESET}")
        for email, result in passed[:10]:
            subj = email.get("subject", "")[:70]
            domain = email.get("domain", "")
            print(f"  {GREEN}• {subj}{RESET}")
            print(f"    {GRAY}from: {domain}{RESET}")
            print(f"    {CYAN}→ {result}{RESET}")

    if blocked:
        print(f"\n{RED}{BOLD}🚫 BLOCKED (would have been noise):{RESET}")
        for email, reason in blocked[:20]:
            subj = email.get("subject", "")[:70]
            domain = email.get("domain", "")
            print(f"  {RED}• {subj}{RESET}")
            print(f"    {GRAY}from: {domain} | reason: {reason}{RESET}")

    if len(blocked) > 20:
        print(f"    {GRAY}... and {len(blocked) - 20} more blocked{RESET}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--since",    type=int, default=30, metavar="DAYS")
    p.add_argument("--category", choices=["recruiting", "finance", "school"], default=None)
    p.add_argument("--accounts", nargs="+", default=None)
    args = p.parse_args()

    accounts = args.accounts or list(ACCOUNTS.keys())

    def fetch(query):
        emails = []
        for acct in accounts:
            try:
                q = f"({query}) newer_than:{args.since}d"
                emails.extend(fetch_emails(q, MAX_RESULTS_PER_QUERY, account=acct))
            except Exception as e:
                print(f"⚠️  {acct}: {e}")
        return emails

    cats = [args.category] if args.category else ["recruiting", "school", "finance"]

    for cat in cats:
        print(f"\nFetching {cat} emails (last {args.since} days)…")
        emails = fetch(GMAIL_QUERIES[cat])
        if cat == "recruiting":
            show(cat, emails, classify_recruiting, _block_reason_recruiting)
        elif cat == "school":
            show(cat, emails, classify_school, _block_reason_school)
        elif cat == "finance":
            show(cat, emails, classify_finance)


if __name__ == "__main__":
    main()
