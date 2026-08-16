# Apply Agent

Human-gated application layer for the job scout. Turns a scored job into a
ready-to-send bundle — tailored resume PDF, cover letter, email draft, and a
blind critic review — without inventing a single fact.

## Pipeline

```
scout job dir (job_description.txt + apply_link.txt)
        │
        ▼
ats_keywords.py   JD analysis: keyword scan vs profile vocab, role family,
                  seniority, dealbreaker flags (Go roles, Founding Engineer,
                  residency-restricted, marketplaces)
        ▼
tailor.py         content-preserving resume tailoring: project blocks and
                  skill lines reordered by JD overlap. NO content changes —
                  only order. Original order recorded in a LaTeX comment.
        ▼
writer.py         cover letter + email draft, template-filled from
                  profile.yaml (verified facts) and the JD itself
        ▼
critic.py         blind review: 1-page PDF, no hyphen-split keywords, JD
                  keyword coverage, every original block intact, no
                  unapproved numbers in drafts
        ▼
apply.py          bundle + tracker.csv row + verdict (APPLY / FLAG / DISCARD)
```

## Usage

```bash
# Generate the bundle for a scout result dir:
python3 apply.py --job ~/job_scout_results/2026-08-16/Some_Company_Role

# After human approval, mark it Applied:
python3 apply.py --job <dir> --approve
```

## Setup

1. `cp profile.example.yaml profile.yaml` — fill with your facts
   (`profile.yaml` is gitignored — never commit it).
2. `config.conf` — point `RESUME_TEX` at your one-page LaTeX resume.
3. Needs: `pdflatex` (texlive), `pymupdf` (`pip install pymupdf`), `pyyaml`.

## Rules

- **Nothing is submitted by this tool.** It produces the bundle and opens
  the apply link. The human sends it. No auto-apply without explicit approval.
- **No invented content.** Tailoring reorders; writing interpolates only
  profile.yaml facts + JD text. The critic enforces this.
- Verdicts: `DISCARD` (hard dealbreaker — do not apply), `FLAG` (seniority
  gap or weak match — apply only with eyes open), `APPLY` (proceed).
