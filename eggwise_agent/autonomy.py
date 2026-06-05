"""Autonomous front-desk actions the agents can invoke from the command bar.

These let the LLM agents actually DO the batch work (not just the UI buttons): draft a
personalized message for every recipient who needs one and queue it for human review.
Nothing auto-sends; a clinician approves from the Outbox. Synthetic data only.
"""
from __future__ import annotations

from . import config, leads_data, outreach, tools


def queue_patient_checkins(audience: str = "at_risk", channel: str = "in-app") -> dict:
    """Autonomously draft a personalized check-in for each patient who needs one and queue
    them for clinician review (Care).

    Args:
        audience: "at_risk" (default) for patients flagged watch/high, or "all".
        channel: "in-app" (default) or "email".

    Drafts are warm and non-clinical (no symptom interpretation) and land in the Outbox
    marked queued_for_review. Never auto-sends. Returns a summary of who was queued.
    """
    rows = tools.list_patients_with_risk()
    if audience != "all":
        rows = [r for r in rows if r["risk_level"] != "stable"]
    queued = []
    for r in rows:
        rep = tools.generate_health_report(r["id"])
        d = outreach.draft_checkin(r["name"], rep, config.CLINIC_NAME, channel)
        outreach.queue_message(r["id"], channel, d["subject"], d["body"], to=r["name"])
        queued.append({"patient": r["name"], "risk_level": r["risk_level"]})
    return {
        "queued": len(queued), "recipients": queued, "channel": channel,
        "status": "queued_for_review",
        "note": "Drafted and queued in the Outbox. A clinician reviews before anything sends.",
    }


def queue_checkin(patient_id: str, channel: str = "in-app") -> dict:
    """Draft a personalized check-in for ONE patient and queue it in the Outbox for the
    clinician to review, edit, and send (Care). Use this whenever asked to draft or write
    a check-in for a patient. The draft is non-clinical and never auto-sends.
    """
    rep = tools.generate_health_report(patient_id)
    if "error" in rep:
        return rep
    d = outreach.draft_checkin(rep["name"], rep, config.CLINIC_NAME, channel)
    rec = outreach.queue_message(patient_id, channel, d["subject"], d["body"], to=rep["name"])
    return {
        "queued": 1, "patient": rep["name"], "channel": channel, "status": "queued_for_review",
        "note": "Drafted and queued. The clinician can edit and send it in the chat or the Outbox.",
        "draft": {"id": rec["id"], "to": rec["to"], "channel": rec["channel"],
                  "subject": rec["subject"], "body": rec["body"]},
    }


def queue_lead_outreach(count: int = 3, channel: str = "email",
                        specialty: str = "", location: str = "") -> dict:
    """Autonomously draft personalized first-contact outreach for the top prospective
    patients and queue them for clinic review (Growth).

    Args:
        count: how many top-ranked leads to draft for (default 3).
        channel: "email" (default) or "in-app".
        specialty, location: clinic context for ranking and personalization.

    Messages are personalized on goal, location, and readiness only, never clinical PHI.
    They land in the Outbox marked queued_for_review. Never auto-sends. Returns a summary.
    """
    ranked = leads_data.rank_leads(specialty, location)[: int(count)]
    queued = []
    for lead_view in ranked:
        lead = leads_data.get_lead(lead_view["id"])
        d = outreach.draft_outreach(lead, clinic=config.CLINIC_NAME, specialty=specialty, channel=channel)
        outreach.queue_message(lead_view["id"], channel, d["subject"], d["body"], to=lead_view["alias"])
        queued.append({"lead": lead_view["alias"], "fit_score": lead_view["fit_score"]})
    return {
        "queued": len(queued), "recipients": queued, "channel": channel,
        "status": "queued_for_review",
        "note": "Drafted and queued in the Outbox. The clinic approves before any outreach sends.",
    }
