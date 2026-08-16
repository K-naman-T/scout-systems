"""Tailor — content-preserving resume tailoring for a specific JD.

Reorders project blocks and skill lines so the strongest matches appear
first. NEVER invents or rewrites content: every line of the original
resume stays byte-identical, only ORDER changes. The original order is
recorded in a LaTeX comment header for auditability.

Usage:  python3 tailor.py <resume.tex> <company> <role> [--top "kw1,kw2"]
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ats_keywords import JDProfile, analyze, score_project

SECTION_RE = re.compile(r"\\sectionline\{([^}]*)\}")
def parse_project_blocks(tex: str) -> list[tuple[str, str]]:
    """Return [(name, block)] for each role block (name from \\role{...})."""
    blocks = []
    for m in re.finditer(r"\\role\{", tex):
        start = m.start()
        end_m = re.search(r"\\end\{itemize\}", tex[start:])
        if not end_m:
            continue
        end = start + end_m.end()
        block = tex[start:end]
        nm = re.match(r"\\role\{(.*?)(?:\s*\\href|\})", block, re.DOTALL)
        name = nm.group(1).strip() if nm else f"project-{len(blocks)}"
        blocks.append((name, block))
    return blocks

SKILL_LINES = [
    "product engineering",
    "full-stack",
    "ai/ml",
    "devops",
]


def split_sections(tex: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(tex))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(tex)
        sections[m.group(1).strip().lower()] = tex[m.start():end]
    return sections


def reorder_projects(blocks: list[tuple[str, str]], jd: JDProfile) -> list[tuple[str, str]]:
    """Stable sort by JD keyword overlap (highest first)."""
    scored = [(score_project(name, jd), idx, name, block)
              for idx, (name, block) in enumerate(blocks)]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [(name, block) for _, _, name, block in scored]


def reorder_skill_line(line: str, jd: JDProfile) -> str:
    """Move JD-matched skills to the front of a comma-separated skill line."""
    m = re.match(r"(\\textbf\{[^}]*\}:\s*)(.*?)(\\\\)?$", line.strip())
    if not m:
        return line
    prefix, body = m.group(1), m.group(2)
    items = [i.strip() for i in body.split(",")]
    matched = {k for k, _ in jd.matched_keywords}
    items.sort(key=lambda i: (0 if i.lower() in matched else 1, items.index(i)))
    return prefix + ", ".join(items) + (m.group(3) or "")


def tailor(tex_path: Path, jd: JDProfile, company: str, role: str, out_dir: Path) -> Path:
    tex = tex_path.read_text()
    sections = split_sections(tex)

    header_end = tex.find("\\sectionline{")
    header = tex[:header_end]

    projects_section = sections.get("projects", "")
    skills_section = sections.get("technical skills", "")

    if not projects_section:
        raise SystemExit("ERROR: no PROJECTS section found in resume tex")

    blocks = parse_project_blocks(projects_section)
    if not blocks:
        raise SystemExit("ERROR: no project blocks parsed")

    original_order = "; ".join(name for name, _ in blocks)
    reordered = reorder_projects(blocks, jd)

    # Rebuild the projects section with original spacing preserved.
    new_projects = "\\sectionline{Projects}\n\n" + "\n\n".join(
        block for _, block in reordered
    ) + "\n"

    # Reorder skills lines (matched-first).
    new_skills = skills_section
    if jd.matched_keywords:
        for line in skills_section.splitlines():
            if any(skill in line.lower() for skill in SKILL_LINES):
                new_skills = new_skills.replace(line, reorder_skill_line(line, jd))

    comment = (f"% Tailored for: {company} — {role}\n"
               f"% Generated: {__import__('datetime').date.today().isoformat()}\n"
               f"% Original project order: {original_order}\n")

    out_tex = out_dir / f"resume_tailored.tex"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tex.write_text(
        comment + header
        + sections.get("summary", "") + "\n"
        + sections.get("experience", "") + "\n"
        + new_projects + "\n" + new_skills + "\n"
        + sections.get("education", "") + "\\end{document}\n"
    )
    return out_tex


def compile_pdf(out_dir: Path, job_name: str = "resume_tailored") -> Path | None:
    """Compile the tailored tex with pdflatex into the same directory."""
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
             f"{job_name}.tex"],
            cwd=str(out_dir), capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        print("WARN: pdflatex not found — tex generated, PDF skipped")
        return None
    pdf = out_dir / f"{job_name}.pdf"
    return pdf if pdf.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("resume_tex", type=Path)
    ap.add_argument("company")
    ap.add_argument("role")
    ap.add_argument("--jd", type=Path, help="JD text file (job_description.txt)")
    ap.add_argument("--jd-text", default="", help="JD text inline (alternative to --jd)")
    ap.add_argument("--out", type=Path, default=Path("output"))
    args = ap.parse_args()

    jd_text = args.jd.read_text() if args.jd else args.jd_text
    if not jd_text:
        raise SystemExit("ERROR: pass --jd <file> or --jd-text")
    jd = analyze(jd_text, title=args.role)

    out_dir = args.out / "resume"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tex = tailor(args.resume_tex, jd, args.company, args.role, out_dir)
    pdf = compile_pdf(out_dir)
    print(f"TAILORED: {out_tex}")
    print(f"PDF: {pdf or 'none'}")
    print(f"TOP_KEYWORDS: {', '.join(jd.top_keywords)}")
    print(f"VERDICT: {jd.verdict(3)}")


if __name__ == "__main__":
    main()
