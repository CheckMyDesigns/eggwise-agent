"""Tools for the EggWise agents.

All data here is SYNTHETIC demo data (Vance / Bay Area Fertility Institute).
Nothing in this file touches the production app, Firestore, or real patients.
This keeps the demo brand-safe and privacy-safe by construction.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> list[dict]:
    with open(_DATA / name, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# Growth agent tools (clinic lead qualification)
# --------------------------------------------------------------------------

def list_inbound_leads() -> list[dict]:
    """Return all inbound clinic leads awaiting qualification.

    Each lead has: id, contact_name, clinic, specialty, location,
    plan_interest, message, submitted_at.
    """
    return _load("sample_leads.json")


def get_lead_details(lead_id: str) -> dict:
    """Return the full record for a single lead by id. Returns {} if not found."""
    for lead in _load("sample_leads.json"):
        if lead.get("id") == lead_id:
            return lead
    return {}


def save_qualified_lead(
    lead_id: str, score: int, tier: str, reasoning: str, draft_outreach: str
) -> dict:
    """Record a qualification decision for a lead.

    Args:
        lead_id: the lead's id.
        score: fit score 0-100.
        tier: one of "hot", "warm", "cold".
        reasoning: short justification for the score.
        draft_outreach: a personalized outreach email DRAFT for human review.

    This never sends anything. It returns the saved record marked as awaiting
    human approval, so a person signs off before any outreach goes out.
    """
    return {
        "lead_id": lead_id,
        "score": score,
        "tier": tier,
        "reasoning": reasoning,
        "draft_outreach": draft_outreach,
        "status": "awaiting_human_approval",
    }


# --------------------------------------------------------------------------
# Care agent tools (clinician copilot, synthetic data only)
# --------------------------------------------------------------------------

def list_patients() -> list[dict]:
    """Return the demo patients (id and name only) a clinician may review."""
    return [{"id": p["id"], "name": p["name"]} for p in _load("sample_patients.json")]


def get_patient_daily_logs(patient_id: str, days: int = 30) -> dict:
    """Return a patient's recent daily logs (synthetic demo data).

    Args:
        patient_id: the patient's id.
        days: how many of the most recent log entries to return.

    Returns a dict with id, name, and a list of log entries, or {} if not found.
    Clinician-facing only.
    """
    for p in _load("sample_patients.json"):
        if p.get("id") == patient_id:
            return {"id": p["id"], "name": p["name"], "logs": p.get("logs", [])[:days]}
    return {}


def propose_followup(patient_id: str, suggested_date: str, reason: str) -> dict:
    """Propose a follow-up appointment for clinician approval.

    Does NOT create a calendar event. Returns a proposal the clinician confirms.
    """
    return {
        "patient_id": patient_id,
        "suggested_date": suggested_date,
        "reason": reason,
        "status": "proposed_pending_clinician_approval",
    }
