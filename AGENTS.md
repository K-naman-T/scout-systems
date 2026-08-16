# Scout Systems — Job Discovery Pipeline

Autonomous job-discovery systems running via Hermes Agent cron jobs: board/ATS scouting, scoring, company due diligence, and a swipe-style review dashboard. Human-gated — discovery only, no auto-applications.

## Systems

### 1. Job Scout — `job-scout/`
- Fetches live tech listings from Remotive, RemoteOK, Arbeitnow, The Muse APIs, scores them against the profile in `profile.conf`, outputs to `~/job_scout_results/`.
- Run: `cd ~/scout-systems/job-scout && python3 job_scout_v3.py`
- Config: edit `profile.conf` for roles, skills, salary, API sources
- Output: `~/job_scout_results/YYYY-MM-DD/` with per-company folders + `~/job_scout_results/job_scout_tracker.csv`
- **Key constraint:** Discovery only — never apply or outreach without explicit confirmation
- **Due diligence:** after every run, independently verify each top candidate company (use `references/due-diligence-template.md` or the copy in `job-scout/`)
- **Delivery:** daily cron, delivers digest to Discord origin

### 2. OSS Scout — `oss-scout/`
- `gh search issues` sweep (label × language) for contribution opportunities across the target stack.
- Output: daily markdown digest of issues grouped by language with direct links.
- Requires authenticated `gh` CLI on the run machine.

### 3. Outreach Tracker — `outreach-tracker/`
- Swipe-style review UI for leads (FastAPI + SQLite).
- Run: `cd ~/scout-systems/outreach-tracker && uvicorn main:app --host 0.0.0.0 --port 8080`
- Routes: `/swipe` (card UI), `/interests` (saved leads), `/` (admin table)
- DB: SQLite (`outreach.db`, gitignored), WAL mode
- Status flow: New → right-swipe → Interested → Applied; New → left-swipe → Skipped
- Auth: users via `OUTREACH_USERS` env var (JSON). Empty = no login (local mode).

## Pipeline

```
Cron (daily scout) → Score + Dedup + Due Diligence → Digest (Discord/chat)
                                → High-scoring leads → outreach-tracker DB → Swipe UI
```

## Rules

- **No applications or outreach without user confirmation. Discovery only.**
- **Company due diligence required** for every top match. Blacklist rules live in `profile.conf` / `due-diligence-template.md`.
- Standalone Python scrapers won't work for LinkedIn/Indeed/Upwork — use agent `web_search` + native X tools instead.
- Scores are suggestions — manually vet before presenting.

## Development & Evolution

- Capture repeatable workflows as Hermes skills.
- The local scout-systems (including the original Hermes-built job_scout) is the living example of this philosophy.

Follow these instructions exactly. When working in subdirectories not listed above, check for additional project instruction files (AGENTS.md, Claude.md, etc.).
