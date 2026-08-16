"""Writer — cover letter + email drafts from verified profile facts only.

Template-driven: every fact interpolated comes from profile.yaml (local,
gitignored) or the JD itself. No invented metrics, no hallucinated projects.
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import yaml

from ats_keywords import JDProfile, analyze, score_project


def load_profile(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def top_projects(profile: dict, jd: JDProfile, n: int = 3) -> list[dict]:
    """Pick the profile projects with the highest JD keyword overlap."""
    scored = []
    for proj in profile.get("projects", []):
        score = score_project(proj["name"], jd)
        scored.append((score, proj))
    scored.sort(key=lambda t: -t[0])
    return [p for _, p in scored[:n] if _ > 0] or profile.get("projects", [])[:1]


def cover_letter(profile: dict, company: str, role: str, jd: JDProfile) -> str:
    p = profile
    projects = top_projects(p, jd)
    keywords = ", ".join(jd.top_keywords[:6]) or "your stack"

    proj_lines = []
    for proj in projects:
        line = f"- {proj['one_liner']}"
        proj_lines.append(line)

    why = f"I built {projects[0]['name']} because {projects[0]['why']}" if projects else ""

    return f"""To: Hiring Team, {company}
Re: {role}

Hi,

I'm {p['name']} — {p['tagline']}. {why}.

Projects most relevant to this role:
{chr(10).join(proj_lines)}

I work in {keywords} daily, and I'm set up for {p['setup_line']}.

{p['availability']}

{p['signoff']}
"""


def email_draft(profile: dict, company: str, role: str, jd: JDProfile, apply_url: str) -> str:
    p = profile
    projects = top_projects(p, jd, n=2)
    names = ", ".join(proj["name"] for proj in projects) or p["fallback_projects"]

    return f"""Subject: {role} — {p['name']}

Hi {company} team,

Applying for the {role} role. I'm a product engineer who ships AI-native
products end-to-end ({p['stack_short']}). Relevant builds: {names}.

CV: attached (tailored to this JD).
Application: {apply_url}

{p['signoff']}
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument("--company", required=True)
    ap.add_argument("--role", required=True)
    ap.add_argument("--jd", type=Path, required=True)
    ap.add_argument("--apply-url", default="")
    ap.add_argument("--out", type=Path, default=Path("output"))
    args = ap.parse_args()

    profile = load_profile(args.profile)
    jd = analyze(args.jd.read_text(), title=args.role)

    out = args.out / "writer"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cover_letter.md").write_text(cover_letter(profile, args.company, args.role, jd))
    (out / "email_draft.md").write_text(
        email_draft(profile, args.company, args.role, jd, args.apply_url))
    print(f"COVER: {out / 'cover_letter.md'}")
    print(f"EMAIL: {out / 'email_draft.md'}")


if __name__ == "__main__":
    main()
