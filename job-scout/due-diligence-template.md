# Company Due Diligence — Reference Template

Copy this per-company table into the digest for each top posting:

```markdown
#### #N: {Job Title} — {Company Name} (Score: {X.X}/100)
| Field | Detail |
|---|---|
| **HQ** | {City, Country} |
| **What it is** | {1-2 line description of product/market} |
| **Stage** | {Bootstrapped / Pre-seed / Seed / Series X / Public / Platform} |
| **Funding** | {Total raised $X, latest round, date} |
| **Role** | {Full title} |
| **Salary** | {Listed salary or N/A} |
| **Location** | {Remote? Global or restricted?} |
| **Requirements** | {Years exp, key techs, level} |
| **Verdict** | {✅ KEEP or ❌ DISCARD + reason} |
```

## Verdict Codes

| Code | Meaning | When |
|------|---------|------|
| ✅ KEEP | Passes all filters, worth user consideration | All checks pass |
| ❌ DISCARD | Has a hard dealbreaker | Any hard rule violated |
| ⚠️ FLAG | Has issues but not dealbreakers | Seniority gap, salary mismatch, market/platform |

## Hard Dealbreakers Reference

<!-- Edit this list to match your profile.conf — examples below -->
- Company owned by the job-seeker's home country (configure your blacklist in `profile.conf`) → ❌
- Requires specific-country residency (Germany/Brazil/US-only remote) → ❌
- Title says "Founding Engineer" → ❌
- Pure ML research / model training → ❌
- 3D/AR/XR → ❌
- Go roles → ❌
- Not a software engineering role (video editor, marketing, etc.) → ❌

## Seniority Mismatch Flags

| JD Title/Requirement | User's Level | Flag |
|---|---|---|
| "Senior" + "4+ years exp" | 2.5 years | ⚠️ Seniority gap |
| "Staff Software Engineer" | 2.5 years | ⚠️ Likely too senior |
| "Tech Lead" | 2.5 years | ⚠️ Likely too senior |
| "Director" | 2.5 years | ⚠️ Almost certainly too senior |
| "Principal" | 2.5 years | ⚠️ Way too senior |
| No seniority requirement in title/JD | 2.5 years | ✅ Worth checking |

## Geographic Restriction Patterns

| JD Language | Interpretation |
|---|---|
| "Remote - Americas, Europe, Israel" | Global remote ✅ |
| "Remote within Germany" | Germany-resident only ❌ |
| "Remote for candidates in Brazil" | Brazil-resident only ❌ |
| "Remote ±3 hours from ET" | Americas timezones ❌ (India is +9:30 ET) |
| "Remote from US" | US-resident only ❌ |
| "Remote worldwide" | Global ✅ |
| "Remote - preference for LATAM" | Restricted but not hard ❌ |
