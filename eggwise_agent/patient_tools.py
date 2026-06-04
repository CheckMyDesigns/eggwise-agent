"""Patient-facing tools for the patient companion agent.

Synthetic demo data only. Booking is a demo stub; in production book_followup
creates a Google Calendar event through the clinic's existing OAuth integration.
"""
from __future__ import annotations

from . import calendar_tools
from .tools import _load


def get_my_adherence(patient_id: str, days: int = 14) -> dict:
    """Return the patient's own recent medication adherence summary.

    Returns name, days_reviewed, doses_missed, missed_dates, and on_track.
    Returns {} if the patient is not found.
    """
    for p in _load("sample_patients.json"):
        if p.get("id") == patient_id:
            logs = p.get("logs", [])[:days]
            missed = [entry["date"] for entry in logs if not entry.get("meds_taken", False)]
            return {
                "id": p["id"],
                "name": p["name"],
                "days_reviewed": len(logs),
                "doses_missed": len(missed),
                "missed_dates": missed,
                "on_track": len(missed) == 0,
            }
    return {}


def book_followup(patient_id: str, preferred_date: str, time: str = "10:00") -> dict:
    """Book a follow-up appointment for the patient on the given date (YYYY-MM-DD).

    Returns a ready-to-add Google Calendar invite link (and .ics) for the patient,
    plus the proposed time the clinic will confirm. In production this creates the
    event through the clinic's existing Calendar OAuth integration.
    """
    res = calendar_tools.schedule_followup(
        patient_id, preferred_date, time, reason="patient-requested follow-up"
    )
    if "error" in res:
        return res
    res["status"] = "ready_to_confirm"
    res["note"] = "Add it to your calendar with the link. The clinic confirms the final time."
    return res


def get_approved_info(topic: str) -> dict:
    """Return clinic-approved information for a logistics or preparation topic.

    Only returns vetted, non-medical content. If nothing matches, returns a
    fallback that offers to escalate to the care team. Never use this to answer
    a medical question.
    """
    topic_l = topic.lower()
    for entry in _load("approved_content.json"):
        if entry["topic"] in topic_l or any(k in topic_l for k in entry.get("keywords", [])):
            return {"topic": entry["topic"], "answer": entry["answer"]}
    return {
        "topic": topic,
        "answer": None,
        "fallback": "I do not have approved info on that. I can flag your care team if you would like.",
    }


def escalate_to_care_team(patient_id: str, concern: str) -> dict:
    """Flag a concern to the patient's care team.

    Use this for ANY clinical or medical question instead of answering it.
    """
    return {
        "patient_id": patient_id,
        "concern": concern,
        "status": "escalated_to_clinician",
        "message": (
            "Your care team has been notified and will follow up. If this is urgent, "
            "please call your clinic or emergency services."
        ),
    }
