"""Outreach Tracker - FastAPI app."""
import os
import sys
from pathlib import Path
from datetime import date

from fastapi import FastAPI, Request, Form, Query, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Ensure we can import database + validators
sys.path.insert(0, str(Path(__file__).parent))
import database as db
from validators import is_x_channel, validate_lead_row

app = FastAPI(title="Outreach Tracker")

# Auth: users come from the OUTREACH_USERS env var as JSON, e.g.
#   OUTREACH_USERS='{"alice": "secret1", "bob": "secret2"}'
# Empty/missing -> no login required (single-user local mode).
import json as _json
_USERS_RAW = os.environ.get("OUTREACH_USERS", "")
USERS = _json.loads(_USERS_RAW) if _USERS_RAW.strip() else {}

def get_current_user(request: Request):
    user = request.cookies.get("user")
    if user not in USERS:
        return None
    return user

def get_user_or_guest(user: str = Depends(get_current_user)):
    if user in USERS:
        return user
    return None  # guest / not logged in

templates = Jinja2Templates(directory=str(Path(__file__).parent))  # HTML templates are in the same dir as main.py (not in subdir "templates/")
# Disable Jinja internal cache at creation time. This avoids "cannot use tuple with dict as key"
# errors in the LRU cache when complex nested dicts (e.g. stats.by_*) are in the render context
# or under certain Starlette/TestClient + Jinja versions. Safe and common for small apps.
if hasattr(templates.env, "cache"):
    templates.env.cache = None


@app.on_event("startup")
async def startup():
    db.init_db()
    try:
        db.ensure_x_columns()  # X-Precise Outreach additive columns (idempotent)
    except Exception:
        pass  # non-fatal for existing installs

    # Robust Jinja loading: disable internal cache to avoid "tuple with dict as key" TypeError
    # when context contains complex nested dicts (e.g. stats.by_status, stats.by_channel)
    # or during TestClient / certain Python+Starlette versions. Fine for this small app.
    if hasattr(templates.env, "cache"):
        templates.env.cache = None

# Simple login routes
@app.get("/login", response_class=HTMLResponse)
async def login_page():
    template = templates.get_template("login.html")
    return HTMLResponse(template.render({"error": None}))


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username in USERS and USERS[username] == password:
        resp = RedirectResponse(url="/swipe", status_code=303)
        resp.set_cookie(key="user", value=username, httponly=True, max_age=60*60*24*7)
        return resp
    template = templates.get_template("login.html")
    return HTMLResponse(
        template.render({"error": "Invalid username or password"}),
        status_code=401,
    )

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("user")
    return resp

# Helper for X-enriched leads (freelance/contract primary per plan)
def _enrich_x_lead(lead_dict):
    if lead_dict.get('x_persona') or is_x_channel(lead_dict.get('channel')) or lead_dict.get('x_handle'):
        lead_dict['is_x'] = True
        ok, reason = validate_lead_row(lead_dict)
        lead_dict['x_url_valid'] = ok
        if not ok:
            lead_dict['x_url_invalid_reason'] = reason
    return lead_dict


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    status: str = Query("All"),
    channel: str = Query("All"),
    search: str = Query(""),
    user: str = Depends(get_user_or_guest),
):
    raw_leads = db.get_leads(
        status=None if status == "All" else status,
        channel=None if channel == "All" else channel,
        search=search or None,
        persona=user,
    )
    leads = [_enrich_x_lead(dict(l)) for l in raw_leads]
    stats = db.get_stats()
    today_iso = date.today().isoformat()
    context = {
        "request": request,
        "leads": leads,
        "stats": stats,
        "counts": db.get_leads_for_swipe(persona=user),
        "statuses": db.STATUSES,
        "channels": db.CHANNELS,
        "current_status": status,
        "current_channel": channel,
        "current_search": search,
        "today_iso": today_iso,
        "user": user,
    }
    # Use env directly to avoid occasional integration quirks with TemplateResponse + complex context in this env
    template = templates.get_template("index.html")
    content = template.render(context)
    return HTMLResponse(content)


@app.get("/lead/{lead_id}", response_class=HTMLResponse)
async def lead_detail(request: Request, lead_id: int, user: str = Depends(get_user_or_guest)):
    lead = db.get_lead(lead_id)
    if not lead:
        return HTMLResponse("Lead not found", status_code=404)
    lead = _enrich_x_lead(lead)
    context = {
        "request": request,
        "lead": lead,
        "counts": db.get_leads_for_swipe(persona=user),
        "statuses": db.STATUSES,
        "channels": db.CHANNELS,
        "today": date.today().isoformat(),
        "user": user,
    }
    template = templates.get_template("detail.html")
    content = template.render(context)
    return HTMLResponse(content)


@app.post("/lead/new")
async def create_lead(
    name: str = Form(...),
    company: str = Form(""),
    role_or_target: str = Form(""),
    channel: str = Form("Other"),
    status: str = Form("New"),
    contacted_date: str = Form(""),
    next_followup: str = Form(""),
    notes: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    value_estimate: str = Form(""),
    url: str = Form(""),
    user: str = Depends(get_user_or_guest),
):
    lead_id = db.create_lead({
        "name": name,
        "company": company,
        "role_or_target": role_or_target,
        "channel": channel,
        "status": status,
        "contacted_date": contacted_date,
        "next_followup": next_followup,
        "notes": notes,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "value_estimate": value_estimate,
        "url": url,
        "x_persona": user,
    })
    return RedirectResponse(f"/lead/{lead_id}", status_code=303)


@app.post("/lead/{lead_id}/edit")
async def edit_lead(
    lead_id: int,
    name: str = Form(...),
    company: str = Form(""),
    role_or_target: str = Form(""),
    channel: str = Form("Other"),
    status: str = Form("New"),
    contacted_date: str = Form(""),
    next_followup: str = Form(""),
    notes: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    value_estimate: str = Form(""),
    url: str = Form(""),
    user: str = Depends(get_user_or_guest),
):
    db.update_lead(lead_id, {
        "name": name,
        "company": company,
        "role_or_target": role_or_target,
        "channel": channel,
        "status": status,
        "contacted_date": contacted_date,
        "next_followup": next_followup,
        "notes": notes,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "value_estimate": value_estimate,
        "url": url,
    })
    return RedirectResponse(f"/lead/{lead_id}", status_code=303)


@app.post("/lead/{lead_id}/delete")
async def delete_lead(lead_id: int, user: str = Depends(get_user_or_guest)):
    db.delete_lead(lead_id)
    return RedirectResponse("/", status_code=303)


@app.post("/lead/{lead_id}/interaction")
async def add_interaction(
    lead_id: int,
    date_str: str = Form(...),
    type_str: str = Form("Note"),
    summary: str = Form(""),
    outcome: str = Form(""),
    user: str = Depends(get_user_or_guest),
):
    db.add_interaction(lead_id, {
        "date": date_str,
        "type": type_str,
        "summary": summary,
        "outcome": outcome,
    })
    return RedirectResponse(f"/lead/{lead_id}", status_code=303)


@app.get("/swipe", response_class=HTMLResponse)
async def swipe_view(request: Request, user: str = Depends(get_user_or_guest)):
    """Tinder-style swipe interface for reviewing leads."""
    counts = db.get_leads_for_swipe(persona=user)
    first_lead = db.get_next_unreviewed(persona=user)
    if first_lead:
        first_lead = _enrich_x_lead(first_lead)
    context = {
        "request": request,
        "counts": counts,
        "first_lead": first_lead,
        "statuses": db.STATUSES,
        "user": user,
    }
    template = templates.get_template("swipe.html")
    content = template.render(context)
    return HTMLResponse(content)


@app.get("/api/next")
def api_next_lead(user: str = Depends(get_user_or_guest)):
    """Get next unreviewed lead as JSON."""
    lead = db.get_next_unreviewed(persona=user)
    if not lead:
        return JSONResponse({"done": True, "lead": None})
    lead = _enrich_x_lead(lead)
    return JSONResponse({"done": False, "lead": lead})


@app.post("/api/swipe/{lead_id}")
def api_swipe(lead_id: int, direction: str = Query(...), user: str = Depends(get_user_or_guest)):
    """Record a swipe direction. direction='right' or 'left'."""
    if direction not in ("right", "left"):
        return JSONResponse({"error": "direction must be 'right' or 'left'"}, status_code=400)
    db.swipe_lead(lead_id, direction)
    return JSONResponse({"ok": True, "status": "Interested" if direction == "right" else "Skipped"})


@app.get("/api/interests")
def api_interests(user: str = Depends(get_user_or_guest)):
    """Get all right-swiped (Interested) leads as JSON."""
    leads = [_enrich_x_lead(l) for l in db.get_interested_leads(persona=user)]
    return JSONResponse({"leads": leads})


@app.get("/interests", response_class=HTMLResponse)
async def interests_view(request: Request, user: str = Depends(get_user_or_guest)):
    """Page showing right-swiped (Interested) leads."""
    leads = [_enrich_x_lead(l) for l in db.get_interested_leads(persona=user)]
    counts = db.get_leads_for_swipe(persona=user)
    context = {
        "request": request,
        "leads": leads,
        "counts": counts,
        "statuses": db.STATUSES,
        "user": user,
    }
    template = templates.get_template("interests.html")
    content = template.render(context)
    return HTMLResponse(content)


app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)
