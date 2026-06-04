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


def _load_firestore() -> list[dict]:
    from google.cloud import firestore

    project = os.environ.get("EGGWISE_LEADS_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    collection = os.environ.get("EGGWISE_LEADS_COLLECTION", "patient_leads")
    client = firestore.Client(project=project)
    out: list[dict] = []
    for doc in client.collection(collection).stream():
        rec = doc.to_dict() or {}
        rec.setdefault("id", doc.id)
        out.append(rec)
    return out


def load_leads() -> list[dict]:
    """Load raw lead records from the configured backend, falling back to JSON."""
    if os.environ.get("EGGWISE_LEADS_BACKEND", "json").lower() == "firestore":
        try:
            leads = _load_firestore()
            if leads:
                return leads
        except Exception:
            pass  # fall back to synthetic JSON if Firestore is unavailable
    with open(_DATA / "sample_patient_leads.json", "r", encoding="utf-8") as f:
        return json.load(f)


def public_view(lead: dict) -> dict:
    """De-identified, non-clinical view safe to render to anyone."""
    return {k: lead.get(k) for k in _PUBLIC_FIELDS if k in lead}


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
    Wellness Score, plus small bonuses for a goal that matches the clinic specialty
    and a location near the clinic. Returns de-identified views with fit_score + reason.
    """
    spec = (specialty or "").lower().strip()
    loc = (location or "").lower().strip()
    ranked: list[dict] = []
    for lead in load_leads():
        score = int(lead.get("wellness_score", 0) or 0)
        reasons = [f"Wellness Score {lead.get('wellness_score')}"]
        goal = (lead.get("goal") or "").lower()
        if spec and (spec in goal or goal in spec):
            score += 8
            reasons.append(f"goal matches {specialty}")
        if loc and loc.split(",")[0] in (lead.get("location") or "").lower():
            score += 6
            reasons.append(f"near {location}")
        item = public_view(lead)
        item["fit_score"] = min(score, 100)
        item["fit_reason"] = ", ".join(reasons)
        ranked.append(item)
    ranked.sort(key=lambda x: x["fit_score"], reverse=True)
    return ranked


def get_lead(lead_id: str) -> dict | None:
    return next((l for l in load_leads() if l.get("id") == lead_id), None)
