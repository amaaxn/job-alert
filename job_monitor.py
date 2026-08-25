#!/usr/bin/env python3
"""
Monitors SimplifyJobs/New-Grad-Positions for new postings matching your
criteria and emails you when one appears.

Data source: the repo's own listings.json, which its GitHub Action refreshes
roughly every 30 minutes from Simplify's database. This is far more reliable
to parse than the generated README table.

Designed to run on a schedule via GitHub Actions
(see .github/workflows/job-alert.yml) — no server or laptop required.
"""

import json
import os
import smtplib
import ssl
import time
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ---------------------------------------------------------------------------
# CONFIG — edit these to match what you're looking for
# ---------------------------------------------------------------------------

LISTINGS_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/"
    "New-Grad-Positions/dev/.github/scripts/listings.json"
)
SEEN_FILE = "seen_ids.json"

# Categories present in the data (as of Aug 2026):
# "Software", "AI/ML/Data", "Hardware", "Quant", "Product",
# "Software Engineering", "Product Management"
CATEGORIES = {"Software", "AI/ML/Data", "Software Engineering", "Quant"}

# Optional: only alert if the job title contains one of these (case-insensitive
# substring match). Leave empty ([]) to match on category alone.
TITLE_KEYWORDS: list[str] = []  # e.g. ["software engineer", "data", "swe"]

# Optional: only alert for these locations (case-insensitive substring match
# against the listing's location list). Leave empty ([]) to match anywhere.
LOCATION_KEYWORDS: list[str] = []  # e.g. ["remote", "new york", "ny"]

# Skip listings older than this many hours (safety net against a stale entry
# flipping back to active=true long after it was first posted).
MAX_AGE_HOURS = 48

# ---------------------------------------------------------------------------


def fetch_listings() -> list[dict]:
    req = urllib.request.Request(LISTINGS_URL, headers={"User-Agent": "job-monitor"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def load_seen():
    """Returns the set of previously-seen IDs, or None if this is the first run."""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return None


def save_seen(ids) -> None:
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(ids), f)


def matches(job: dict) -> bool:
    if not job.get("active"):
        return False
    if job.get("category") not in CATEGORIES:
        return False
    if TITLE_KEYWORDS:
        title = job.get("title", "").lower()
        if not any(k.lower() in title for k in TITLE_KEYWORDS):
            return False
    if LOCATION_KEYWORDS:
        locs = " ".join(job.get("locations", [])).lower()
        if not any(k.lower() in locs for k in LOCATION_KEYWORDS):
            return False
    age_hours = (time.time() - job.get("date_posted", 0)) / 3600
    if age_hours > MAX_AGE_HOURS:
        return False
    return True


def format_email(jobs: list[dict]) -> str:
    lines = [f"{len(jobs)} new posting(s) matching your filters:\n"]
    for j in jobs:
        posted = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(j["date_posted"]))
        locs = ", ".join(j.get("locations") or ["Location N/A"])
        lines.append(
            f"- {j['company_name']} — {j['title']}\n"
            f"  {locs} | posted {posted}\n"
            f"  {j['url']}\n"
        )
    return "\n".join(lines)


def send_email(body: str, count: int) -> None:
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("EMAIL_TO", sender)

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = f"{count} new grad posting(s) match your filters"
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=context)
        server.login(sender, password)
        server.sendmail(sender, to, msg.as_string())


def main() -> None:
    listings = fetch_listings()
    seen = load_seen()
    all_ids = {j["id"] for j in listings}

    if seen is None:
        # First run: baseline only. Don't email a backlog of hundreds of
        # already-active listings.
        save_seen(all_ids)
        print(f"First run: baselined {len(all_ids)} listings. No email sent.")
        return

    new_matches = [j for j in listings if j["id"] not in seen and matches(j)]

    # Advance the seen set regardless of whether anything matched, so we
    # never re-check the same old entries.
    save_seen(all_ids)

    if new_matches:
        new_matches.sort(key=lambda j: j["date_posted"], reverse=True)
        body = format_email(new_matches)
        send_email(body, len(new_matches))
        print(f"Sent email for {len(new_matches)} new matching posting(s).")
    else:
        print("No new matches this run.")


if __name__ == "__main__":
    main()
