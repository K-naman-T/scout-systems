"""Validation for X-scout outputs — reject demo/fabricated citations before seeding."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

# Handles used only in local demo fixtures — must never reach production DB.
DEMO_HANDLES = frozenset({
    "demoagentbuilder",
    "founderinfra",
    "agentconsult",
    "policyimpact",
})

# Obvious placeholder status IDs from x_scout.py demo block.
DEMO_STATUS_IDS = frozenset({
    "1234567890",
    "987654321",
    "555000222",
    "555000111",
})

X_STATUS_RE = re.compile(
    r"^https?://(?:www\.)?(?:x\.com|twitter\.com)/(?P<handle>[A-Za-z0-9_]{1,15})/status/(?P<status_id>\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)

X_CHANNEL_MARKERS = (
    "platform (x)",
    "x (warm network",
    "x/twitter",
    "(x)",
)


def is_x_channel(channel: str | None) -> bool:
    c = (channel or "").lower()
    return any(m in c for m in X_CHANNEL_MARKERS) or c.startswith("x ")


def parse_x_post_url(url: str | None) -> dict[str, str] | None:
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    m = X_STATUS_RE.match(url)
    if not m:
        return None
    return {
        "handle": m.group("handle").lower(),
        "status_id": m.group("status_id"),
        "url": url,
    }


def is_demo_x_signal(signal: dict[str, Any]) -> bool:
    """True if signal is from the built-in demo fixture set."""
    if signal.get("is_demo"):
        return True
    if signal.get("source") == "demo":
        return True
    handle = (signal.get("handle") or "").lstrip("@").lower()
    if handle in DEMO_HANDLES:
        return True
    parsed = parse_x_post_url(signal.get("url"))
    if not parsed:
        return False
    if parsed["handle"] in DEMO_HANDLES:
        return True
    if parsed["status_id"] in DEMO_STATUS_IDS:
        return True
    return False


def validate_x_post_url(url: str | None) -> tuple[bool, str]:
    """
    Validate an x.com post URL for seeding/digest inclusion.
    Returns (ok, reason).
    """
    if not url or not str(url).strip():
        return False, "missing_url"

    url = str(url).strip()
    # Fast-path: reject known demo URLs even if handle length breaks X format rules.
    for handle in DEMO_HANDLES:
        if f"/{handle}/" in url.lower():
            return False, f"demo_handle:{handle}"
    for sid in DEMO_STATUS_IDS:
        if f"/status/{sid}" in url:
            return False, f"demo_status_id:{sid}"

    parsed = parse_x_post_url(url)
    if not parsed:
        return False, "invalid_x_url_format"

    handle = parsed["handle"]
    status_id = parsed["status_id"]

    if handle in DEMO_HANDLES:
        return False, f"demo_handle:{handle}"

    if status_id in DEMO_STATUS_IDS:
        return False, f"demo_status_id:{status_id}"

    # Real Twitter/X snowflake IDs are typically 15–22 digits.
    if len(status_id) < 15:
        return False, f"status_id_too_short:{len(status_id)}_digits"

    if not status_id.isdigit():
        return False, "status_id_not_numeric"

    return True, "ok"


def validate_signal_for_seed(signal: dict[str, Any]) -> tuple[bool, str]:
    """Gate DB seeding — demo and unverifiable citations are rejected."""
    if is_demo_x_signal(signal):
        return False, "demo_signal"

    if signal.get("verified") is not True and signal.get("source") not in ("x_api", "x_tool", "xurl"):
        # Standalone/demo runs lack real tool provenance.
        if not signal.get("verified"):
            return False, "unverified_source"

    ok, reason = validate_x_post_url(signal.get("url"))
    if not ok:
        return False, reason

    if not (signal.get("text") or "").strip():
        return False, "missing_post_text"

    handle = (signal.get("handle") or "").lstrip("@").strip()
    if not handle:
        return False, "missing_handle"

    return True, "ok"


def validate_lead_row(lead: dict[str, Any]) -> tuple[bool, str]:
    """Validate a row from outreach.db for X channel leads."""
    is_x = is_x_channel(lead.get("channel")) or lead.get("x_handle") or lead.get("x_post_id")
    if not is_x:
        return True, "not_x_lead"

    url = lead.get("url")
    if is_x or lead.get("x_post_id"):
        ok, reason = validate_x_post_url(url)
        if not ok:
            return False, reason

    notes = (lead.get("notes") or "").lower()
    if "(demo" in notes or "demo —" in notes:
        return False, "demo_notes"

    return True, "ok"