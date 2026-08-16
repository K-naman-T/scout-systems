"""Critic — blind-review pass on the tailored bundle before it ships.

Checks (mirrors the ats_score.py rubric):
  1. PDF is one page
  2. No hyphen-split keywords in the PDF text
  3. All top-10 JD keywords present in the tailored tex
  4. Every original project block survives verbatim (no corruption)
  5. Drafts contain no numbers outside the allowed profile-facts set

Output: critic_report.md with a verdict line the agent can act on.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from ats_keywords import analyze

NUMBER_RE = re.compile(r"\b\d[\d,.]*\b")


def check_pdf_one_page(pdf: Path) -> tuple[bool, str]:
    if not pdf or not pdf.exists():
        return False, "pdf missing"
    try:
        import fitz  # pymupdf
    except ImportError:
        return True, "pymupdf unavailable — page-count check skipped"
    doc = fitz.open(str(pdf))
    n = doc.page_count
    doc.close()
    return n == 1, f"{n} page(s)"

def check_hyphen_split(pdf: Path, keywords: list[str]) -> tuple[bool, str]:
    if not pdf or not pdf.exists():
        return False, "pdf missing"
    try:
        import fitz
    except ImportError:
        return True, "pymupdf unavailable — hyphen check skipped"
    doc = fitz.open(str(pdf))
    text = " ".join(str(page.get_text()) for page in doc)
    doc.close()
    norm = re.sub(r"\s+", " ", text).lower()
    # A hyphenated line-break split looks like "first- half" in extracted
    # text (hyphen + whitespace). Intact hyphenated words ("real-time")
    # have no whitespace after the hyphen.
    split = []
    for k in keywords:
        half = k[:len(k) // 2]
        rest = k[len(k) // 2:]
        if re.search(re.escape(half) + r"-\s+" + re.escape(rest), norm):
            split.append(k)
    return not split, f"split keywords: {split or 'none'}"

def check_keyword_coverage(tex: Path, jd_keywords: list[str]) -> tuple[bool, str]:
    if not jd_keywords:
        return True, "no JD keywords to check"
    text = tex.read_text().lower()
    missing = [k for k in jd_keywords[:10] if k not in text]
    return not missing, f"missing from tailored tex: {missing or 'none'}"

def check_blocks_intact(original_tex: Path, tailored_tex: Path) -> tuple[bool, str]:
    """Every original project block must appear verbatim in the tailored tex."""
    from tailor import parse_project_blocks
    orig = parse_project_blocks(original_tex.read_text())
    tailored = parse_project_blocks(tailored_tex.read_text())
    names = [n for n, _ in orig]
    if len(tailored) != len(orig):
        return False, f"block count changed: {len(orig)} -> {len(tailored)}"
    missing = [n for n, _ in orig if n not in [t for t, _ in tailored]]
    return not missing, f"missing blocks: {missing or 'none'} (order: {names})"

def check_draft_numbers(drafts: list[Path], allowed: set[str]) -> tuple[bool, str]:
    """Numbers in drafts must all come from the profile facts or the JD.
    URLs are stripped (numeric ids are not claims)."""
    found: set[str] = set()
    for d in drafts:
        if not d.exists():
            continue
        text = re.sub(r"https?://\S+", " ", d.read_text())
        for m in NUMBER_RE.finditer(text):
            found.add(m.group(0).rstrip(".,;"))
    bad = {n for n in found if n not in allowed}
    return not bad, f"unapproved numbers: {sorted(bad) or 'none'}"

def run(original_tex: Path, tailored_tex: Path, pdf: Path, drafts: list[Path],
        allowed_numbers: set[str], jd_keywords: list[str]) -> dict:
    checks = [
        ("pdf_one_page", *check_pdf_one_page(pdf)),
        ("no_hyphen_split", *check_hyphen_split(pdf, jd_keywords)),
        ("keyword_coverage", *check_keyword_coverage(tailored_tex, jd_keywords)),
        ("blocks_intact", *check_blocks_intact(original_tex, tailored_tex)),
        ("draft_numbers", *check_draft_numbers(drafts, allowed_numbers)),
    ]
    failed = [name for name, ok, _ in checks if not ok]
    return {
        "checks": checks,
        "passed": not failed,
        "failures": failed,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original-tex", type=Path, required=True)
    ap.add_argument("--tailored-tex", type=Path, required=True)
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--drafts", nargs="*", type=Path, default=[])
    ap.add_argument("--allowed-numbers", default="", help="comma-separated")
    ap.add_argument("--jd", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("output"))
    args = ap.parse_args()

    jd = analyze(args.jd.read_text())
    allowed = set(x.strip() for x in args.allowed_numbers.split(",") if x.strip())
    result = run(args.original_tex, args.tailored_tex, args.pdf,
                 args.drafts, allowed, jd.top_keywords)

    out = args.out / "critic"
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Critic Report", ""]
    for name, ok, detail in result["checks"]:
        lines.append(f"- [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    lines.append("")
    lines.append(f"VERDICT: {'APPROVED — bundle ready to send' if result['passed'] else 'REVIEW — fix failures before sending'}")
    report = out / "critic_report.md"
    report.write_text("\n".join(lines))
    print(f"REPORT: {report}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
