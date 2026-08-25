# New Grad Simplify Job Alert Tracker

Emails you when a matching new-grad role shows up on
[SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions).

- Watches `listings.json` about every 30 minutes
- Emails only **new** matches (first run is a baseline, not a dump)
- Finds roles. Does not apply for you
- A job must pass every filter you turn on (category, title, and location)
- `JOB_MATCH_ANY` is the exception: one hit is enough (ex. FAANG+ *or* NY *or* NJ)

## Use it for your own email

- Fork or copy this repo
- Create a Gmail [App Password](https://myaccount.google.com/apppasswords) (2-Step Verification on)
- Add secrets: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `EMAIL_TO`
- Optional variables (unset = off): `JOB_CATEGORIES`, `JOB_TITLE_KEYWORDS`, `JOB_LOCATION_KEYWORDS`, `JOB_MATCH_ANY` (example: `faang,NY,NJ`)
- Enable the workflow from the Actions tab if GitHub disabled it on the fork

