"""Shared lead-data access for the console (and parity with the MCP lead server).

Backend selection mirrors mcp_leads_server.py:
  EGGWISE_LEADS_BACKEND = "json" (default, synthetic) | "firestore"
The console reads leads directly here for speed; the Growth agent reads them over MCP.
Consent gating is enforced here too: clinical fields are stripped from the public view.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"

# Non-clinical fields safe to display and to use when personalizing outreach.
_PUBLIC_FIELDS = ("id", "alias", "age", "location", "goal", "wellness_score",
                  "signals", "payment", "consented_to_share")
# Clinical fields revealed only for leads with consented_to_share = true.
_CLINICAL_FIELDS = ("amh", "bmi", "prior_treatment", "diagnosis")


_FS_CLIENT = None
_LEADS_CACHE = None


def firestore_client():
    """Return a cached Firestore client. Creating one per request (auth + connection
    setup) is the slow part, so we build it once per process."""
    global _FS_CLIENT
    if _FS_CLIENT is None:
        from google.cloud import firestore
        _FS_CLIENT = firestore.Client(
            project=os.environ.get("EGGWISE_LEADS_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return _FS_CLIENT


def _load_firestore() -> list[dict]:
    collection = os.environ.get("EGGWISE_LEADS_COLLECTION", "patient_leads")
    out: list[dict] = []
    for doc in firestore_client().collection(collection).stream():
        rec = doc.to_dict() or {}
        rec.setdefault("id", doc.id)
        out.append(rec)
    return out


def load_leads() -> list[dict]:
    """Load lead records once and cache them. Leads are static reference data, so
    re-reading the backend on every request (and on every re-rank) just adds latency."""
    global _LEADS_CACHE
    if _LEADS_CACHE is not None:
        return _LEADS_CACHE
    leads = None
    if os.environ.get("EGGWISE_LEADS_BACKEND", "json").lower() == "firestore":
        try:
            leads = _load_firestore() or None
        except Exception:
            leads = None
    if leads is None:
        with open(_DATA / "sample_patient_leads.json", "r", encoding="utf-8") as f:
            leads = json.load(f)
    _LEADS_CACHE = leads
    return _LEADS_CACHE


def public_view(lead: dict) -> dict:
    """De-identified, non-clinical view. The full name appears only for leads who
    consented to share; everyone else stays initials until they consent."""
    view = {k: lead.get(k) for k in _PUBLIC_FIELDS if k in lead}
    view["display"] = lead.get("name") if (lead.get("consented_to_share") and lead.get("name")) else lead.get("alias")
    return view


def detail_view(lead: dict) -> dict:
    """Public view plus clinical fields, but only if the patient consented to share."""
    view = public_view(lead)
    if lead.get("consented_to_share"):
        view["clinical"] = {k: lead.get(k) for k in _CLINICAL_FIELDS if k in lead}
        view["clinical_visible"] = True
    else:
        view["clinical"] = None
        view["clinical_visible"] = False
        view["clinical_note"] = "Clinical profile unlocks once the patient consents to share."
    return view


def rank_leads(specialty: str = "", location: str = "") -> list[dict]:
    """Rank prospective patients by fit. Deterministic so the board is stable:
    Wellness Score, plus a goal-matches-specialty bonus and a location bonus
    (same city, then same state). Returns de-identified views with fit_score + reason.
    """
    spec = (specialty or "").lower().strip()
    loc = (location or "").lower().strip()
    loc_city = loc.split(",")[0].strip()
    loc_state = loc.split(",")[-1].strip() if "," in loc else ""
    ranked: list[dict] = []
    for lead in load_leads():
        score = int(lead.get("wellness_score", 0) or 0)
        reasons = [f"Wellness Score {lead.get('wellness_score')}"]
        goal = (lead.get("goal") or "").lower()
        if spec and (spec in goal or goal in spec):
            score += 10
            reasons.append(f"goal matches {specialty}")
        ll = (lead.get("location") or "").lower()
        if loc_city and loc_city in ll:
            score += 12
            reasons.append(f"in {location}")
        elif loc_state and ll.endswith(loc_state):
            score += 6
            reasons.append(f"in-state ({loc_state.upper()})")
        item = public_view(lead)
        item["fit_score"] = min(score, 100)
        item["fit_reason"] = ", ".join(reasons)
        ranked.append(item)
    ranked.sort(key=lambda x: x["fit_score"], reverse=True)
    return ranked


def get_lead(lead_id: str) -> dict | None:
    return next((l for l in load_leads() if l.get("id") == lead_id), None)
