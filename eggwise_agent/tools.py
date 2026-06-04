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


# Symptoms a front desk should surface (not interpret) for clinician review.
_WATCH_SYMPTOMS = ("pelvic pain", "severe pain", "heavy bleeding", "severe cramping",
                   "shortness of breath", "chest pain")


def _summarize_logs(logs: list[dict]) -> dict:
    """Compute adherence, streak, symptom frequency, and mood trend from daily logs.

    Logs are expected newest-first (as in the demo data)."""
    from collections import Counter

    n = len(logs)
    taken = sum(1 for e in logs if e.get("meds_taken"))
    adherence = round(taken / n, 2) if n else 0.0
    missed_dates = [e.get("date") for e in logs if not e.get("meds_taken")]

    streak = 0
    for e in logs:  # leading run of taken doses (most recent first)
        if e.get("meds_taken"):
            streak += 1
        else:
            break

    recent_missed = 0
    for e in logs:
        if not e.get("meds_taken"):
            recent_missed += 1
        else:
            break

    sym = Counter()
    for e in logs:
        for s in e.get("symptoms", []) or []:
            sym[s] += 1
    symptom_counts = dict(sym.most_common())

    moods = [e["mood"] for e in logs if isinstance(e.get("mood"), (int, float))]
    avg_mood = round(sum(moods) / len(moods), 1) if moods else None
    trend = "steady"
    if len(moods) >= 4:
        half = len(moods) // 2
        recent_avg = sum(moods[:half]) / half
        older_avg = sum(moods[half:]) / (len(moods) - half)
        if recent_avg - older_avg >= 0.5:
            trend = "improving"
        elif older_avg - recent_avg >= 0.5:
            trend = "declining"

    return {
        "logs_reviewed": n,
        "adherence_rate": adherence,
        "current_streak_days": streak,
        "recent_consecutive_missed": recent_missed,
        "doses_missed": len(missed_dates),
        "missed_dates": missed_dates,
        "symptom_counts": symptom_counts,
        "avg_mood": avg_mood,
        "mood_trend": trend,
    }


def _risk_flags(s: dict) -> list[str]:
    flags: list[str] = []
    if s["logs_reviewed"] and s["adherence_rate"] < 0.8:
        flags.append(f"Adherence {int(s['adherence_rate'] * 100)}% is below the 80% target.")
    if s["recent_consecutive_missed"] >= 2:
        flags.append(f"{s['recent_consecutive_missed']} most-recent consecutive doses missed.")
    for symptom, count in s["symptom_counts"].items():
        if any(w in symptom.lower() for w in _WATCH_SYMPTOMS):
            flags.append(f"Symptom for clinician review: {symptom} ({count}x). Surfaced, not interpreted.")
    if s["avg_mood"] is not None and s["avg_mood"] <= 2.5:
        flags.append(f"Low average mood ({s['avg_mood']}/5).")
    if s["mood_trend"] == "declining":
        flags.append("Mood trend declining over the period.")
    return flags


def _render_report_md(name: str, patient_id: str, s: dict, flags: list[str]) -> str:
    syms = ", ".join(f"{k} ({v}x)" for k, v in s["symptom_counts"].items()) or "none logged"
    flag_md = "\n".join(f"- {f}" for f in flags) if flags else "- None. Patient looks stable on logged data."
    return (
        f"# EggWise Health Report: {name}\n"
        f"*Patient {patient_id} | {s['logs_reviewed']} day(s) reviewed | synthetic demo data*\n\n"
        f"## Adherence\n"
        f"- Medication adherence: **{int(s['adherence_rate'] * 100)}%**\n"
        f"- Current streak: **{s['current_streak_days']} day(s)**\n"
        f"- Doses missed: {s['doses_missed']}"
        + (f" ({', '.join(s['missed_dates'])})" if s["missed_dates"] else "")
        + "\n\n"
        f"## Symptoms\n- {syms}\n\n"
        f"## Mood\n- Average: {s['avg_mood'] if s['avg_mood'] is not None else 'n/a'}/5, trend: {s['mood_trend']}\n\n"
        f"## Flags for clinician review\n{flag_md}\n\n"
        f"> Surfaced for a clinician to review. Not a diagnosis. Requires clinician sign-off before any action."
    )


def generate_health_report(patient_id: str, days: int = 30) -> dict:
    """Generate a structured health report and a clinician-ready markdown summary
    from a patient's daily logs (Care, synthetic data).

    Surfaces adherence, current streak, symptom frequency, mood trend, and risk
    flags for clinician review. It does not diagnose: it surfaces, it does not
    conclude. Returns structured fields plus report_markdown.
    """
    patient = next((p for p in _load("sample_patients.json") if p.get("id") == patient_id), None)
    if not patient:
        return {"error": f"Patient '{patient_id}' not found."}
    logs = patient.get("logs", [])[:days]
    s = _summarize_logs(logs)
    flags = _risk_flags(s)
    s.update({
        "id": patient_id,
        "name": patient["name"],
        "risk_flags": flags,
        "report_markdown": _render_report_md(patient["name"], patient_id, s, flags),
    })
    return s
