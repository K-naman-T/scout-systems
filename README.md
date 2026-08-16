# Scout Systems — Job Discovery Pipeline

Autonomous job-discovery systems running on Hermes Agent (by Nous Research): board/ATS scouting, scoring, company due diligence, and a swipe-style review dashboard. Human-gated — discovery only, no auto-applications.

## Modules

### 1. Job Scout — `job-scout/`
- Fetches live tech listings from Remotive, RemoteOK, Arbeitnow, The Muse APIs (+ direct ATS scraping via Greenhouse/Lever/Ashby).
- Scores every listing against your profile (`profile.conf`) with weighted keyword matching (title 25 / skills 30 / remote 15 / salary 15 / company size 5 / industry 10).
- Outputs per-company folders (JD, match score, apply link) + a CSV tracker.
- **Key constraint:** Discovery only — never apply or outreach without explicit user confirmation.

```bash
cd job-scout && python3 job_scout_v3.py
```

### 2. OSS Scout — `oss-scout/`
- `gh search issues` sweep (label × language) for `good first issue` / `help wanted` issues across Python, TypeScript, JavaScript, Rust, Go — feeds real open-source contribution opportunities.
- Requires authenticated `gh` CLI.

```bash
python3 oss-scout/scout.py
```

### 3. Outreach Tracker — `outreach-tracker/`
- Tinder-style swipe UI for reviewing leads (FastAPI + SQLite + vanilla HTML/JS).
- Routes: `/swipe` (card UI), `/interests` (saved leads), `/` (admin table).
- Status flow: New → right-swipe → Interested → Applied; New → left-swipe → Skipped.
- Auth: users come from the `OUTREACH_USERS` env var as JSON (`{"alice": "secret1"}`). Empty = no login (single-user local mode).

```bash
cd outreach-tracker && OUTREACH_USERS='{}' uvicorn main:app --host 0.0.0.0 --port 8080
```

## Pipeline

```
Cron (daily scout) → Score + Dedup + Due Diligence → Digest (Discord/chat)
                                → High-scoring leads → outreach-tracker DB → Swipe UI
```

## Rules

- **No applications or outreach without user confirmation. Discovery only.**
- **Company due diligence required** for every top match (see `job-scout/due-diligence-template.md`).
- Standalone scrapers don't work for LinkedIn/Indeed/Upwork — use agent `web_search` + native X tools instead.
- Scores are suggestions — manually vet before presenting.

## Built with Hermes Agent

This system was built autonomously with Hermes Agent (skills, cron jobs, terminal, memory). Each module is self-contained so it can run on any machine with Python 3.11+ and an authenticated `gh` CLI where needed.
