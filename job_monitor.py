#!/usr/bin/env python3
"""Email new SimplifyJobs/New-Grad-Positions postings that match your filters.

Reads listings.json; run on a schedule via GitHub Actions."""

import ast
import json
import os
import re
import smtplib
import ssl
import time
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ---------------------------------------------------------------------------
# CONFIG — filters from optional env vars (unset = off / match everything):
#
#   JOB_CATEGORIES              e.g. "Software,AI/ML/Data,Software Engineering,Quant"
#   JOB_TITLE_KEYWORDS          e.g. "swe,data"
#   JOB_LOCATION_KEYWORDS       e.g. "remote"
#   JOB_MATCH_ANY               e.g. "faang,NY,NJ"   (OR: FAANG+ and/or US states)
# ---------------------------------------------------------------------------

LISTINGS_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/"
    "New-Grad-Positions/dev/.github/scripts/listings.json"
)
UTIL_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/"
    "New-Grad-Positions/dev/.github/scripts/util.py"
)
SEEN_FILE = "seen_ids.json"


def _env_set(name: str) -> set[str]:
    val = os.environ.get(name, "").strip()
    return {v.strip() for v in val.split(",") if v.strip()}


def _env_list(name: str) -> list[str]:
    val = os.environ.get(name, "").strip()
    return [v.strip() for v in val.split(",") if v.strip()]


# Empty = no restriction. Values: Software, AI/ML/Data, Hardware, Quant, Product, ...
CATEGORIES = _env_set("JOB_CATEGORIES")

TITLE_KEYWORDS = _env_list("JOB_TITLE_KEYWORDS")

# Don't put state abbreviations here — substring match false-positives (Sunnyvale, Germany).
LOCATION_KEYWORDS = _env_list("JOB_LOCATION_KEYWORDS")

# OR-group: job matches if it hits any token. "faang" uses Simplify's list;
# 2-letter codes match as US states. Unset = this filter is off.
MATCH_ANY = _env_list("JOB_MATCH_ANY")

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
}
_STATE_SUFFIX = {
    code: re.compile(rf",\s*{code}\s*$", re.IGNORECASE) for code in US_STATES
}
# Names that appear without a ", ST" suffix in the listings data.
STATE_ALIASES = {
    "NY": re.compile(r"(^new york$)|(\bnyc\b)|(new york city)", re.IGNORECASE),
    "NJ": re.compile(r"^new jersey$", re.IGNORECASE),
}

# Ignore listings older than this (guards against a stale active=true flip).
MAX_AGE_HOURS = 72

# ---------------------------------------------------------------------------


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "job-monitor"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode()


def fetch_listings() -> list[dict]:
    return json.loads(_fetch(LISTINGS_URL))


def fetch_faang_plus() -> set[str]:
    """Parse FAANG_PLUS from Simplify's util.py."""
    tree = ast.parse(_fetch(UTIL_URL))
    for node in tree.body:
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if any(isinstance(t, ast.Name) and t.id == "FAANG_PLUS" for t in targets):
            parsed = ast.literal_eval(value)
            if isinstance(parsed, (set, list, tuple, frozenset)):
                return {str(v).lower() for v in parsed}
            raise RuntimeError("FAANG_PLUS in util.py is not a set/list")
    raise RuntimeError("Could not find FAANG_PLUS in Simplify util.py")


def load_seen():
    """Previously-seen IDs, or None on first run."""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return None


def save_seen(ids) -> None:
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(ids), f)


def _matches_state(locations: list[str], code: str) -> bool:
    suffix = _STATE_SUFFIX[code]
    alias = STATE_ALIASES.get(code)
    return any(
        suffix.search(loc) or (alias and alias.search(loc)) for loc in locations
    )


def _matches_token(job: dict, token: str, faang_plus: set[str]) -> bool:
    t = token.strip()
    if t.lower() in ("faang", "faang+"):
        return job.get("company_name", "").lower() in faang_plus
    code = t.upper()
    if code in US_STATES:
        return _matches_state(job.get("locations") or [], code)
    locs = " ".join(job.get("locations") or []).lower()
    return t.lower() in locs


def matches(job: dict, faang_plus: set[str]) -> bool:
    if not job.get("active"):
        return False
    if not job.get("url"):
        return False
    if CATEGORIES and job.get("category") not in CATEGORIES:
        return False
    if TITLE_KEYWORDS:
        title = job.get("title", "").lower()
        if not any(k.lower() in title for k in TITLE_KEYWORDS):
            return False
    if LOCATION_KEYWORDS:
        locs = " ".join(job.get("locations", [])).lower()
        if not any(k.lower() in locs for k in LOCATION_KEYWORDS):
            return False
    if MATCH_ANY and not any(
        _matches_token(job, tok, faang_plus) for tok in MATCH_ANY
    ):
        return False
    age_hours = (time.time() - job.get("date_posted", 0)) / 3600
    if age_hours > MAX_AGE_HOURS:
        return False
    return True


def format_email(jobs: list[dict], faang_plus: set[str]) -> str:
    lines = [f"{len(jobs)} new posting(s) matching your filters:\n"]
    for j in jobs:
        posted = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(j["date_posted"]))
        locs = ", ".join(j.get("locations") or ["Location N/A"])
        name = j["company_name"]
        if name.lower() in faang_plus:
            name = f"🔥 {name}"
        lines.append(
            f"- {name} — {j['title']}\n"
            f"  {locs} | posted {posted}\n"
            f"  {j.get('url') or 'URL N/A'}\n"
        )
    return "\n".join(lines)


def send_email(body: str, count: int) -> None:
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("EMAIL_TO", sender)

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = f"[GITHUB JOB TRACKER] {count} new grad posting(s) match your filters"
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
        # First run: baseline only, don't email the backlog.
        save_seen(all_ids)
        print(f"First run: baselined {len(all_ids)} listings. No email sent.")
        return

    faang_plus = fetch_faang_plus()
    print(f"Loaded {len(faang_plus)} FAANG+ companies from Simplify util.py.")
    new_matches = [
        j for j in listings if j["id"] not in seen and matches(j, faang_plus)
    ]

    # Always advance seen so we never re-check old entries.
    save_seen(all_ids)

    if new_matches:
        new_matches.sort(key=lambda j: j["date_posted"], reverse=True)
        body = format_email(new_matches, faang_plus)
        send_email(body, len(new_matches))
        print(f"Sent email for {len(new_matches)} new matching posting(s).")
    else:
        print("No new matches this run.")


if __name__ == "__main__":
    main()
