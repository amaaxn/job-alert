# new-grad-job-alert

Watches [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions)
and emails you the moment a posting matching your filters shows up — no
manual checking, no server, no laptop that has to stay on. It runs on
GitHub Actions' free scheduler.

It reads the repo's own `listings.json` (refreshed by their bot every ~30
min from Simplify's database) rather than scraping the generated README, so
it's parsing structured data, not scraping HTML.

## Setup (5 minutes)

1. **Create a new GitHub repo** (private is fine) and push these files to it,
   or use "Use this template" / copy these files into a repo of your own.

2. **Generate a Gmail App Password** (this is what lets the script send mail
   as you without your real password):
   - Turn on 2-Step Verification on your Google account if it isn't already:
     https://myaccount.google.com/security
   - Go to https://myaccount.google.com/apppasswords
   - Create one named e.g. "job-alert", copy the 16-character password.

3. **Add repo secrets** — in your new repo: Settings → Secrets and variables
   → Actions → New repository secret. Add:
   - `GMAIL_ADDRESS` — the Gmail address you generated the app password for
   - `GMAIL_APP_PASSWORD` — the 16-character app password from step 2
   - `EMAIL_TO` — where you want alerts sent (can be the same address)

4. **Edit the filters** at the top of `job_monitor.py` — `CATEGORIES`,
   `TITLE_KEYWORDS`, `LOCATION_KEYWORDS` — to match what you're looking for.
   Defaults are set to Software / AI-ML-Data / Software Engineering / Quant,
   no keyword or location restriction.

5. **Commit and push.** The workflow runs automatically every 30 minutes.
   The very first run only takes a baseline snapshot of everything currently
   active (so you don't get an email with 3,000 jobs in it) — you'll start
   getting alerts on genuinely new postings from the second run onward.

   You can also trigger a run manually anytime from the repo's Actions tab
   ("New-Grad Job Alert" → Run workflow) to test it without waiting.

## Notes

- The upstream `url` field points straight to whatever ATS the company
  uses (Workday, Greenhouse, Lever, a custom portal, etc.) — this only
  automates *finding out about* a posting, not filling out or submitting
  the application. Use Simplify autofill (or handle it manually) once
  you're on the page.
- `seen_ids.json` is what the workflow commits back each run to remember
  what it's already alerted you about — don't delete it, or you'll get
  re-alerted on everything currently active.
- If you ever want to pause it, disable the workflow from the Actions tab
  rather than deleting the repo.
