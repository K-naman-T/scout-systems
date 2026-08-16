"""Apply Agent — deterministic JD analysis for the job-application pipeline.

Extracts keywords from a job description against a profile skill vocabulary,
classifies the role family, and raises dealbreaker/seniority signals.

Pure stdlib. No LLM calls — the agent layer (Hermes cron) does the writing;
this module only computes facts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Profile vocabulary — mirrors job-scout profile.conf target_skills.
PROFILE_SKILLS = [
    "python", "typescript", "javascript", "react", "node.js", "node",
    "docker", "shell", "fastapi", "django", "flask", "postgresql",
    "postgres", "mongodb", "aws", "kubernetes", "k8s", "git", "ci/cd",
    "rest api", "rest", "graphql", "ai agents", "agents", "agentic",
    "llm", "llms", "rag", "voice", "speech-to-text", "stt", "tts",
    "full-stack", "full stack", "devops", "autonomous agents",
    "product engineering", "microservices", "mcp", "realtime", "real-time",
    "websocket", "sse", "next.js", "nextjs", "tailwind", "pytorch",
    "computer vision", "asr", "multimodal", "langchain", "vector",
    "embeddings", "orchestration", "streaming", "state machine", "rbac",
]

ROLE_FAMILIES = {
    "backend": ["fastapi", "django", "flask", "postgres", "postgresql", "mongodb",
                "microservices", "rest api", "kubernetes", "docker", "graphql",
                "distributed", "high-throughput", "scalable", "api"],
    "ai-agent": ["agentic", "ai agents", "agents", "llm", "llms", "rag", "mcp",
                 "langchain", "orchestration", "autonomous", "embeddings",
                 "vector", "multimodal", "tools"],
    "fullstack": ["react", "typescript", "javascript", "node.js", "next.js",
                  "frontend", "tailwind", "web", "ui"],
    "voice": ["voice", "stt", "tts", "asr", "speech", "twilio", "realtime audio"],
    "ml": ["pytorch", "computer vision", "hyperspectral", "spectral", "ml",
           "machine learning", "cv", "model"],
    "infra": ["docker", "kubernetes", "aws", "ci/cd", "linux", "terraform",
              "observability", "gcp", "azure"],
}

HARD_DEALBREAKERS = {
    "go_role": ["golang", "go language", "written in go", "pioneer go"],
    "founding_engineer": ["founding engineer"],
    "residency_restricted": [
        r"\bremote\s+(?:in|within|only for|only to|for candidates in)",
        r"\bcandidates?\s+(?:in|from|based in)\s+[A-Z][a-z]+",
        r"\bmust\s+be\s+based\s+in",
        r"\b(?:US|USA|Germany|Brazil|EU|UK)\s*(?:timezone|only|based)",
        r"\b(?:us|usa|german|brazilian|uk)\s+(?:timezone|hours|working hours)",
        r"work\s+authorization\s+required",
        r"sponsorship\s+not\s+available",
    ],
    "marketplace": ["lemon.io", "toptal", "a.team", "upwork", "arc.dev"],
}

SENIORITY_RE = re.compile(r"(\d{1,2})\+?\s*(?:years?|yrs?)", re.IGNORECASE)


@dataclass
class JDProfile:
    matched_keywords: list[tuple[str, int]] = field(default_factory=list)
    role_family: str = "unknown"
    family_scores: dict[str, int] = field(default_factory=dict)
    seniority_years: int = 0
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def top_keywords(self) -> list[str]:
        return [k for k, _ in self.matched_keywords[:12]]

    def verdict(self, profile_years: int) -> str:
        """APPLY | FLAG | DISCARD"""
        if any(f in ("go_role", "founding_engineer", "residency_restricted",
                     "marketplace") for f in self.flags):
            return "DISCARD"
        if self.seniority_years and self.seniority_years >= profile_years + 3:
            return "FLAG"
        if not self.matched_keywords:
            return "FLAG"
        return "APPLY"


def _tokenize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def analyze(jd_text: str, title: str = "", profile_skills: list[str] | None = None) -> JDProfile:
    """Analyze a JD: keyword matches, role family, seniority, dealbreakers."""
    text = _tokenize(jd_text)
    skills = profile_skills or PROFILE_SKILLS
    result = JDProfile()

    # Keyword frequency scan (word-boundary aware).
    for skill in skills:
        esc = re.escape(skill)
        hits = len(re.findall(rf"\b{esc}\b", text)) if " " not in skill else text.count(skill)
        if hits:
            result.matched_keywords.append((skill, hits))
    result.matched_keywords.sort(key=lambda kv: (-kv[1], kv[0]))

    # Role family scoring.
    for family, terms in ROLE_FAMILIES.items():
        score = sum(text.count(re.escape(t)) for t in terms)
        result.family_scores[family] = score
    if result.family_scores:
        result.role_family = max(result.family_scores, key=lambda k: result.family_scores[k])  # type: ignore[arg-type]
        top = result.family_scores[result.role_family]
        if top == 0:
            result.role_family = "unknown"

    # Seniority.
    years = [int(m.group(1)) for m in SENIORITY_RE.finditer(text)]
    if years:
        result.seniority_years = max(years)

    # Dealbreakers.
    low = text
    if any(t in low for t in HARD_DEALBREAKERS["go_role"]):
        result.flags.append("go_role")
    if title and "founding engineer" in title.lower():
        result.flags.append("founding_engineer")
    for pat in HARD_DEALBREAKERS["residency_restricted"]:
        if re.search(pat, text, re.IGNORECASE):
            result.flags.append("residency_restricted")
            break
    if any(t in low for t in HARD_DEALBREAKERS["marketplace"]):
        result.flags.append("marketplace")

    # Notes.
    if result.seniority_years:
        result.notes.append(f"JD asks {result.seniority_years}+ years; profile has 3")
    if not result.matched_keywords:
        result.notes.append("zero profile-skill matches in this JD")
    if result.role_family != "unknown":
        result.notes.append(f"dominant role family: {result.role_family}")

    return result


def project_keyword_map() -> dict[str, list[str]]:
    """Project name -> profile-vocab keywords the project exercises.
    Derived from the resume's own project descriptions (verified facts only).
    """
    return {
        "spectral match": ["python", "fastapi", "react", "docker", "ml",
                           "spectral", "rest api", "web ui", "api"],
        "codepulse": ["python", "mcp", "tree-sitter", "sqlite", "d3",
                      "ai agents", "coding agents", "cli", "graph"],
        "open ore mapper": ["python", "ml", "spectral", "geospatial", "classical",
                            "benchmark", "pipeline"],
        "smb voice agent": ["voice", "stt", "tts", "twilio", "fastapi",
                            "react", "ai agents", "gemini", "telephony"],
        "techex ai": ["react", "typescript", "websocket", "sse", "voice",
                      "gemini", "realtime", "llm", "streaming", "duplex"],
        "fixforge": ["next.js", "react", "typescript", "prisma", "tailwind",
                     "marketplace", "fullstack", "full-stack"],
    }


def score_project(project_name: str, jd: JDProfile) -> int:
    """Keyword-overlap score for a project against the JD analysis."""
    pkeys = project_keyword_map().get(project_name.lower().strip(), [])
    matched = {k for k, _ in jd.matched_keywords}
    return sum(1 for k in pkeys if k in matched)
