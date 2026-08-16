"""Apply Agent — orchestrator.

End-to-end per-job pipeline (deterministic core, agent does the rest):
  JD → keyword analysis → resume tailoring (PDF) → cover letter + email
      → critic blind-review → approval bundle + tracker row.

Usage:
  python3 apply.py --job <scout-job-dir> [--approve]
  --approve marks the tracker row Applied (run AFTER user approval).

The job dir is a job-scout output folder containing job_description.txt
and apply_link.txt. Human gate: nothing is submitted anywhere by this
script — it produces the bundle + opens the apply link for the user.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ats_keywords import analyze  # noqa: E402
from critic import run as critic_run  # noqa: E402
from tailor import tailor, compile_pdf  # noqa: E402
from writer import cover_letter, email_draft, load_profile  # noqa: E402

BASE = Path(__file__).parent


def read_config() -> dict:
    cfg = {}
    cfg_path = BASE / "config.conf"
    if cfg_path.exists():
        for line in cfg_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def parse_job_dir(job_dir: Path) -> dict:
    jd = (job_dir / "job_description.txt").read_text()
    title = ""
    company = job_dir.name
    for line in jd.splitlines():
        if line.lower().startswith("job title:"):
            title = line.split(":", 1)[1].strip()
        if line.lower().startswith("company:"):
            company = line.split(":", 1)[1].strip() or company
    apply_url = ""
    link_file = job_dir / "apply_link.txt"
    if link_file.exists():
        apply_url = link_file.read_text().strip()
    return {"jd": jd, "title": title, "company": company, "apply_url": apply_url}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", type=Path, required=True, help="job-scout result dir")
    ap.add_argument("--approve", action="store_true",
                    help="mark the tracker row Applied (after human approval)")
    args = ap.parse_args()

    cfg = read_config()
    resume_tex = Path(cfg.get("RESUME_TEX", "~/.hermes/resume/zuke_resume.tex")).expanduser()
    profile_path = Path(cfg.get("PROFILE_YAML", BASE / "profile.yaml")).expanduser()
    if not resume_tex.exists():
        raise SystemExit(f"ERROR: resume tex not found: {resume_tex}")
    if not profile_path.exists():
        raise SystemExit(f"ERROR: profile not found: {profile_path} (copy profile.example.yaml)")

    job = parse_job_dir(args.job)
    profile = load_profile(profile_path)
    jd = analyze(job["jd"], title=job["title"])
    profile_years = int(profile.get("experience_years", 3))

    slug = re.sub(r"[^a-z0-9]+", "-", job["company"].lower()).strip("-")
    out = BASE / "output" / f"{slug}-{date.today().isoformat()}"
    out.mkdir(parents=True, exist_ok=True)

    verdict = jd.verdict(profile_years)

    if args.approve:
        append_tracker(BASE / "tracker.csv", slug, job, jd, verdict, "Applied")
        print(f"APPROVED: {slug} marked Applied in tracker.csv")
        return

    # 1. Tailor + PDF.
    tailored_tex = tailor(resume_tex, jd, job["company"], job["title"], out / "resume")
    pdf = compile_pdf(out / "resume")

    # 2. Write drafts.
    (out / "writer").mkdir(parents=True, exist_ok=True)
    (out / "writer" / "cover_letter.md").write_text(
        cover_letter(profile, job["company"], job["title"], jd))
    (out / "writer" / "email_draft.md").write_text(
        email_draft(profile, job["company"], job["title"], jd, job["apply_url"]))

    # 3. Critic.
    import re as _re
    _num = _re.compile(r"\b\d[\d,.]*\b")
    allowed = set(profile.get("allowed_numbers", []))
    allowed |= {m.group(0).rstrip(".,;") for m in _num.finditer(profile_path.read_text())}
    allowed |= {m.group(0).rstrip(".,;") for m in _num.finditer(job["jd"])}
    allowed |= {str(y) for y in range(2020, 2031)}
    drafts = [out / "writer" / "cover_letter.md", out / "writer" / "email_draft.md"]
    critic = critic_run(resume_tex, tailored_tex, pdf, drafts, allowed, jd.top_keywords)
    (out / "critic" / "critic_report.md").parent.mkdir(parents=True, exist_ok=True)
    report_lines = ["# Critic Report", ""]
    for name, ok, detail in critic["checks"]:
        report_lines.append(f"- [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    report_lines.append("")
    report_lines.append(f"VERDICT: {verdict} — {'bundle ready' if critic['passed'] and verdict in ('APPLY','FLAG') else 'review needed'}")
    (out / "critic" / "critic_report.md").write_text("\n".join(report_lines))

    # 4. Manifest.
    manifest = {
        "company": job["company"], "role": job["title"], "date": date.today().isoformat(),
        "apply_url": job["apply_url"], "verdict": verdict,
        "role_family": jd.role_family, "top_keywords": jd.top_keywords,
        "flags": jd.flags, "seniority_years": jd.seniority_years,
        "critic_passed": critic["passed"], "critic_failures": critic["failures"],
    }
    (out / "application.json").write_text(json.dumps(manifest, indent=2))

    append_tracker(BASE / "tracker.csv", slug, job, jd, verdict, "New")

    print(f"COMPANY: {job['company']} | ROLE: {job['title']}")
    print(f"VERDICT: {verdict} (flags: {jd.flags or 'none'}, seniority: {jd.seniority_years or 'n/a'}y)")
    print(f"FAMILY: {jd.role_family} | TOP: {', '.join(jd.top_keywords[:8])}")
    print(f"BUNDLE: {out}")
    print(f"PDF: {pdf or 'none'}")
    print(f"CRITIC: {'PASS' if critic['passed'] else 'FAIL — ' + str(critic['failures'])}")
    if job["apply_url"]:
        print(f"APPLY: {job['apply_url']}")
    if verdict == "DISCARD":
        print("NOTE: verdict is DISCARD — do not apply without overriding.")
    print("NEXT: reply 'approve' to mark Applied and move to submission.")


def append_tracker(tracker: Path, slug: str, job: dict, jd, verdict: str, status: str) -> None:
    import re as _re
    row = [
        datetime.utcnow().isoformat(timespec="seconds"),
        slug, job["company"], job["title"], verdict, status,
        jd.role_family, " ".join(jd.top_keywords[:8]),
        str(jd.seniority_years), job["apply_url"],
    ]
    new = not tracker.exists()
    with tracker.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "slug", "company", "role", "verdict",
                        "status", "role_family", "top_keywords",
                        "seniority_years", "apply_url"])
        w.writerow(row)


if __name__ == "__main__":
    main()
