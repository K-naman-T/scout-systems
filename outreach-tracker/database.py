"""SQLite database layer for outreach tracker."""
import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "outreach.db")

STATUSES = [
    "New",
    "Interested",
    "Skipped",
    "Applied",
    "To Contact",
    "Contacted",
    "Follow-up",
    "Meeting",
    "Closed Won",
    "Closed Lost",
]

CHANNELS = [
    "Warm Network (Alumni Lab)",
    "Warm Network (Past Employer)",
    "Warm Network (Founders)",
    "Warm Network (CPL)",
    "Warm Network (PPG)",
    "Warm Network (Alumni)",
    "Warm Network (Project)",
    "Cold (Think Tank)",
    "Cold (Political Consultancy)",
    "Cold (CSR/Mining)",
    "Cold (Dev Consulting)",
    "Platform (LinkedIn)",
    "Platform (Upwork)",
    "Platform (Substack)",
    "Platform (X/Twitter)",
    "X (Warm Network / Signals)",
    "Other",
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT DEFAULT '',
            role_or_target TEXT DEFAULT '',
            channel TEXT DEFAULT 'Other',
            status TEXT DEFAULT 'To Contact',
            contacted_date TEXT DEFAULT '',
            next_followup TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            contact_email TEXT DEFAULT '',
            contact_phone TEXT DEFAULT '',
            value_estimate TEXT DEFAULT '',
            url TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            date TEXT NOT NULL DEFAULT (date('now')),
            type TEXT NOT NULL DEFAULT 'Note',
            summary TEXT NOT NULL DEFAULT '',
            outcome TEXT DEFAULT '',
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


def get_leads(status=None, channel=None, search=None, persona=None):
    conn = get_db()
    query = "SELECT * FROM leads"
    params = []
    conditions = []

    if status and status != "All":
        conditions.append("status = ?")
        params.append(status)
    if channel and channel != "All":
        conditions.append("channel = ?")
        params.append(channel)
    if search:
        conditions.append("(name LIKE ? OR company LIKE ? OR notes LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s])
    if persona:
        conditions.append("x_persona = ?")
        params.append(persona)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_lead(lead_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        conn.close()
        return None

    lead = dict(row)
    lead["interactions"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM interactions WHERE lead_id = ? ORDER BY date DESC, id DESC",
            (lead_id,),
        ).fetchall()
    ]
    conn.close()
    return lead


def create_lead(data: dict):
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    x_persona = data.get("x_persona", "")
    if x_persona:
        cur = conn.execute(
            """INSERT INTO leads (name, company, role_or_target, channel, status,
               contacted_date, next_followup, notes, contact_email, contact_phone,
               value_estimate, url, created_at, updated_at, x_persona)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("name", ""),
                data.get("company", ""),
                data.get("role_or_target", ""),
                data.get("channel", "Other"),
                data.get("status", "New"),
                data.get("contacted_date", ""),
                data.get("next_followup", ""),
                data.get("notes", ""),
                data.get("contact_email", ""),
                data.get("contact_phone", ""),
                data.get("value_estimate", ""),
                data.get("url", ""),
                now,
                now,
                x_persona,
            ),
        )
    else:
        cur = conn.execute(
            """INSERT INTO leads (name, company, role_or_target, channel, status,
               contacted_date, next_followup, notes, contact_email, contact_phone,
               value_estimate, url, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("name", ""),
                data.get("company", ""),
                data.get("role_or_target", ""),
                data.get("channel", "Other"),
                data.get("status", "New"),
                data.get("contacted_date", ""),
                data.get("next_followup", ""),
                data.get("notes", ""),
                data.get("contact_email", ""),
                data.get("contact_phone", ""),
                data.get("value_estimate", ""),
                data.get("url", ""),
                now,
                now,
            ),
        )
    lead_id = cur.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def update_lead(lead_id: int, data: dict):
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    allowed = {
        "name", "company", "role_or_target", "channel", "status",
        "contacted_date", "next_followup", "notes", "contact_email",
        "contact_phone", "value_estimate", "url",
    }
    sets = []
    params = []
    for k, v in data.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        conn.close()
        return
    sets.append("updated_at = ?")
    params.append(now)
    params.append(lead_id)

    conn.execute(
        f"UPDATE leads SET {', '.join(sets)} WHERE id = ?", params
    )
    conn.commit()
    conn.close()


def delete_lead(lead_id: int):
    conn = get_db()
    conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()


def add_interaction(lead_id: int, data: dict):
    conn = get_db()
    conn.execute(
        """INSERT INTO interactions (lead_id, date, type, summary, outcome)
           VALUES (?, ?, ?, ?, ?)""",
        (
            lead_id,
            data.get("date", date.today().isoformat()),
            data.get("type", "Note"),
            data.get("summary", ""),
            data.get("outcome", ""),
        ),
    )
    # Also update lead's updated_at
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("UPDATE leads SET updated_at = ? WHERE id = ?", (now, lead_id))
    conn.commit()
    conn.close()


def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    by_status = {
        r["status"]: r["cnt"]
        for r in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM leads GROUP BY status"
        ).fetchall()
    }
    by_channel = {
        r["channel"]: r["cnt"]
        for r in conn.execute(
            "SELECT channel, COUNT(*) as cnt FROM leads GROUP BY channel"
        ).fetchall()
    }
    today_followups = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE next_followup = date('now')"
    ).fetchone()[0]
    overdue_followups = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE next_followup != '' AND next_followup < date('now') AND status NOT IN ('Closed Won', 'Closed Lost')"
    ).fetchone()[0]
    conn.close()
    return {
        "total": total,
        "by_status": by_status,
        "by_channel": by_channel,
        "today_followups": today_followups,
        "overdue_followups": overdue_followups,
    }


def get_unreviewed_leads(persona=None):
    """Get leads that haven't been swiped on yet (status='New')."""
    conn = get_db()
    query = "SELECT * FROM leads WHERE status = 'New'"
    params = []
    if persona:
        query += " AND x_persona = ?"
        params.append(persona)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_next_unreviewed(persona=None):
    """Get the first unreviewed lead (for swipe queue)."""
    conn = get_db()
    query = "SELECT * FROM leads WHERE status = 'New'"
    params = []
    if persona:
        query += " AND x_persona = ?"
        params.append(persona)
    query += " ORDER BY created_at ASC LIMIT 1"
    row = conn.execute(query, params).fetchone()
    conn.close()
    return dict(row) if row else None


def swipe_lead(lead_id: int, direction: str):
    """Record a swipe decision. direction='right' → Interested, 'left' → Skipped."""
    new_status = "Interested" if direction == "right" else "Skipped"
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, now, lead_id),
    )
    conn.commit()
    conn.close()


def get_interested_leads(persona=None):
    """Get all right-swiped (Interested) leads."""
    conn = get_db()
    query = "SELECT * FROM leads WHERE status = 'Interested'"
    params = []
    if persona:
        query += " AND x_persona = ?"
        params.append(persona)
    query += " ORDER BY updated_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_leads_for_swipe(persona=None):
    """Get counts for the swipe view header."""
    conn = get_db()
    query_pending = "SELECT COUNT(*) FROM leads WHERE status = 'New'"
    query_interested = "SELECT COUNT(*) FROM leads WHERE status = 'Interested'"
    params = []
    if persona:
        query_pending += " AND x_persona = ?"
        query_interested += " AND x_persona = ?"
        params = [persona, persona]
    pending = conn.execute(query_pending, params[:1] if persona else []).fetchone()[0]
    interested = conn.execute(query_interested, params[1:] if persona else []).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    conn.close()
    return {"pending": pending, "interested": interested, "total": total}


# ------------------------------------------------------------------
# X-Precise Outreach extensions (safe, additive)
# Add X signal columns via migration or ALTER when first run.
# These are nullable and backward compatible.
# ------------------------------------------------------------------

X_LEAD_COLUMNS = [
    "x_handle TEXT",
    "x_user_id TEXT",
    "x_bio TEXT",
    "x_followers INTEGER",
    "x_verified INTEGER DEFAULT 0",
    "x_overall_score REAL",
    "x_score_breakdown TEXT",
    "x_signals_explain TEXT",
    "x_recent_posts_summary TEXT",
    "x_engagement_likes INTEGER",
    "x_engagement_reposts INTEGER",
    "x_engagement_replies INTEGER",
    "x_due_diligence_summary TEXT",
    "x_source_queries TEXT",
    "x_persona TEXT",
    "x_last_activity TEXT",
    "x_post_id TEXT",
    "x_signal_type TEXT",  # direct_hire | pain_point | milestone | first_engineer | contract_gig (freelance primary)
]

def ensure_x_columns():
    """Idempotent: add X outreach columns if missing. Call on startup."""
    conn = get_db()
    existing = {row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
    for col_def in X_LEAD_COLUMNS:
        col = col_def.split()[0]
        if col not in existing:
            try:
                conn.execute(f"ALTER TABLE leads ADD COLUMN {col_def}")
            except Exception:
                pass  # column may have been added concurrently
    conn.commit()
    conn.close()

def get_x_high_signal_leads(limit=50):
    """Convenience: recent high-signal X leads (for future dedicated views)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM leads WHERE x_persona IS NOT NULL OR channel LIKE '%X%' ORDER BY updated_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
