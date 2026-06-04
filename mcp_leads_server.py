"""Standalone MCP server exposing EggWise patient-lead tools for the Growth agent.

Growth is lead generation FOR fertility doctors and clinics: it surfaces prospective
patients (suspected leads) with their Wellness Scores so a clinic can find the
patients who best fit its practice.

Backend (env EGGWISE_LEADS_BACKEND):
  - "json" (default): reads data/sample_patient_leads.json (synthetic, de-identified).
  - "firestore": reads a Firestore collection read-only, schema-agnostic.
    Config: EGGWISE_LEADS_PROJECT (default GOOGLE_CLOUD_PROJECT),
            EGGWISE_LEADS_COLLECTION (default "patient_leads").

Transport (env EGGWISE_MCP_TRANSPORT): "stdio" (default) or "http" / "sse".
  EGGWISE_MCP_HOST (default 127.0.0.1), EGGWISE_MCP_PORT (default 8765).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

_DATA = Path(__file__).resolve().parent / "data"
_BACKEND = os.environ.get("EGGWISE_LEADS_BACKEND", "json").lower()
_HOST = os.environ.get("EGGWISE_MCP_HOST", "127.0.0.1")
_PORT = int(os.environ.get("EGGWISE_MCP_PORT", "8765"))

mcp = FastMCP("eggwise-leads", host=_HOST, port=_PORT)


def _load_json() -> list[dict]:
    with open(_DATA / "sample_patient_leads.json", "r", encoding="utf-8") as f:
        return json.load(f)


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


def _load() -> list[dict]:
    if _BACKEND == "firestore":
        try:
            leads = _load_firestore()
            if leads:
                return leads
        except Exception:
            pass  # fall back to bundled synthetic JSON if Firestore is unavailable
    return _load_json()


@mcp.tool()
def list_patient_leads() -> list[dict]:
    """Return prospective patients (suspected leads) with their Wellness Scores and
    attributes (alias, age, location, goal, signals, payment). De-identified until
    the clinic engages."""
    return _load()


@mcp.tool()
def get_patient_lead(lead_id: str) -> dict:
    """Return one prospective patient by id, or {} if not found."""
    for lead in _load():
        if lead.get("id") == lead_id:
            return lead
    return {}


@mcp.tool()
def save_match(lead_id: str, clinic: str, fit_score: int, reason: str) -> dict:
    """Record that a clinic should pursue a prospective patient.

    fit_score is 0-100. reason is the one-line rationale for why this clinic is the
    best fit for the patient. This does not contact the patient; it returns a record
    awaiting the clinic's outreach approval.
    """
    return {
        "lead_id": lead_id,
        "clinic": clinic,
        "fit_score": fit_score,
        "reason": reason,
        "status": "awaiting_clinic_outreach",
    }


@mcp.tool()
def save_outreach_draft(lead_id: str, channel: str, subject: str, message: str) -> dict:
    """Save a DRAFT first-contact outreach message for a prospective patient, awaiting
    clinic approval.

    channel is "email" or "in-app" (delivered through the EggWise Fertility Tracker app).
    The message must NOT contain clinical PHI (AMH, BMI, diagnosis, lab values), even for a
    consented lead: personalize only on goal, location, and readiness. This never sends; it
    returns a record for a human to review and approve before any outreach goes out.
    """
    return {
        "lead_id": lead_id,
        "channel": channel,
        "subject": subject,
        "message": message,
        "status": "draft_awaiting_clinic_approval",
        "note": "Not sent. A human reviews and approves before any outreach.",
    }


def _transport() -> str:
    t = os.environ.get("EGGWISE_MCP_TRANSPORT", "stdio").lower()
    if t in ("http", "streamable-http"):
        return "streamable-http"
    if t == "sse":
        return "sse"
    return "stdio"


if __name__ == "__main__":
    mcp.run(transport=_transport())
