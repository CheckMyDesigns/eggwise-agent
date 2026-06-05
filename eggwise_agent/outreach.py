"""Outreach drafting (Gemini, consent-aware, PHI-free) and a simulated outbox.

draft_outreach writes a personalized first-contact message for a prospective patient,
on the non-clinical signals only (goal, location, readiness). It never includes clinical
PHI, even for consented leads, because an outreach message to the patient should not.
If the model call fails (no credentials), it falls back to a clean template so the
console still works offline.

The outbox is an in-memory, per-instance store: "sending" records the message and marks
it sent. Nothing leaves the system. In production this maps to the clinic's email
provider and the EggWise Fertility Tracker in-app messaging.
"""
from __future__ import annotations

from datetime import datetime

_MODEL = "gemini-2.5-flash"
_client = None


def _genai():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client()  # uses Vertex env: GOOGLE_GENAI_USE_VERTEXAI, project, location
    return _client


def _template(lead: dict, clinic: str, specialty: str, channel: str) -> dict:
    goal = lead.get("goal", "fertility care")
    loc = lead.get("location", "your area")
    body = (
        f"Hello,\n\n"
        f"I'm reaching out from {clinic}. We specialize in {specialty or 'fertility care'}, "
        f"and we would love to support you with {goal}. We work with people near {loc} and "
        f"would be glad to answer your questions and help you take the next step whenever you "
        f"feel ready.\n\n"
        f"If you'd like, you can book a no-pressure consult with our team.\n\n"
        f"Warmly,\n{clinic}"
    )
    if channel == "in-app":
        return {"channel": "in-app", "subject": "", "body": body}
    return {"channel": "email", "subject": f"{clinic}: support for your {goal} journey", "body": body}


def draft_outreach(lead: dict, clinic: str = "your clinic", specialty: str = "",
                   channel: str = "email") -> dict:
    """Draft a warm, consent-aware, PHI-free first-contact message for a lead.

    Returns {channel, subject, body}. Uses Gemini, with a template fallback so the
    console is robust even without model credentials.
    """
    chan = "in-app" if channel == "in-app" else "email"
    goal = lead.get("goal", "")
    loc = lead.get("location", "")
    signals = lead.get("signals", "")
    fmt = ('Return "Subject: <subject line>" on the first line, then a blank line, then the body.'
           if chan == "email" else "Return only the message body, with no subject line.")
    prompt = (
        f"Write a SHORT, warm, professional first-contact {chan} from {clinic}, a fertility "
        f"clinic specializing in {specialty or 'fertility care'}, to a prospective patient who "
        f"uses the EggWise Fertility Tracker app.\n"
        f"Explain in 2 to 3 sentences why the clinic is a great fit for this person, then invite "
        f"them to book a consult.\n"
        f"Personalize ONLY on these non-clinical details: goal={goal!r}, location={loc!r}, "
        f"readiness signals={signals!r}.\n"
        f"HARD RULES: Never mention or imply any clinical or medical data (no AMH, BMI, "
        f"diagnosis, lab values). Give no medical advice. No emojis. Address the reader "
        f"generically with no name. Sign off as {clinic!r}.\n{fmt}"
    )
    try:
        text = (_genai().models.generate_content(model=_MODEL, contents=prompt).text or "").strip()
        if not text:
            raise ValueError("empty response")
        if chan == "email":
            subject, body = "", text
            if text.lower().startswith("subject:"):
                first, _, rest = text.partition("\n")
                subject = first.split(":", 1)[1].strip()
                body = rest.strip()
            if not subject:
                subject = f"{clinic}: support for your {goal or 'fertility'} journey"
            return {"channel": "email", "subject": subject, "body": body}
        return {"channel": "in-app", "subject": "", "body": text}
    except Exception:
        return _template(lead, clinic, specialty, chan)


def draft_checkin(patient_name: str, summary: dict, clinic: str = "your clinic",
                  channel: str = "in-app") -> dict:
    """Draft a warm, NON-CLINICAL patient check-in from the clinic, personalized on
    engagement only (adherence, streak, missed doses). It never references or interprets
    symptoms and gives no medical advice. Ends noting clinician review. Gemini + template
    fallback. Returns {channel, subject, body}.
    """
    name = (patient_name or "there").split(" (")[0]
    adh = int(round((summary.get("adherence_rate") or 0) * 100))
    streak = summary.get("current_streak_days") or 0
    missed = summary.get("doses_missed") or 0
    tone = ("Gently acknowledge it has been a busy stretch with a couple of missed doses and offer support."
            if missed > 0 else f"Warmly celebrate their consistency (a {streak}-day streak).")
    prompt = (
        f"Write a SHORT, warm check-in {channel} from {clinic} to a fertility patient named {name}. "
        f"{tone} Invite them to reply or book time if anything has come up. "
        f"Do NOT give medical advice, do NOT mention or interpret any symptoms, do NOT include lab "
        f"values. End with a final line exactly: This message requires clinician review before sending.\n"
        f"Return \"Subject: <subject>\" on the first line, a blank line, then the body."
    )
    try:
        text = (_genai().models.generate_content(model=_MODEL, contents=prompt).text or "").strip()
        if not text:
            raise ValueError("empty")
        subject, body = "", text
        if text.lower().startswith("subject:"):
            first, _, rest = text.partition("\n")
            subject = first.split(":", 1)[1].strip()
            body = rest.strip()
        if not subject:
            subject = f"Checking in from {clinic}"
        return {"channel": channel, "subject": subject, "body": body}
    except Exception:
        opener = ("We noticed a couple of missed doses recently and want to make sure you have what you need."
                  if missed > 0 else f"You have kept a wonderful {streak}-day streak, really nice work.")
        body = (f"Hi {name},\n\nWe're checking in from {clinic}. {opener} If anything has come up or you "
                f"have questions, just reply and our team will help. We're with you on this journey.\n\n"
                f"This message requires clinician review before sending.")
        return {"channel": channel, "subject": f"Checking in from {clinic}", "body": body}


# --------------------------------------------------------------------------
# Simulated outbox. Nothing actually sends. Persists to Firestore when the
# Firestore backend is configured (survives Cloud Run cold starts and scaling);
# falls back to an in-memory list locally or if Firestore is unavailable.
# --------------------------------------------------------------------------
_OUTBOX: list[dict] = []
_seq = 0
_OUTBOX_COLL = "agent_outbox"


def _outbox_fs():
    import os
    if os.environ.get("EGGWISE_LEADS_BACKEND", "").lower() != "firestore":
        return None
    try:
        from google.cloud import firestore
        return firestore.Client(
            project=os.environ.get("EGGWISE_LEADS_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    except Exception:
        return None


def _persist(rec: dict) -> None:
    _OUTBOX.append(rec)  # always keep an in-instance copy
    fs = _outbox_fs()
    if fs:
        try:
            fs.collection(_OUTBOX_COLL).add(dict(rec))
        except Exception:
            pass  # durability is best-effort; the in-memory copy still serves this instance


def send_outreach(lead_id: str, channel: str, subject: str, body: str, to: str = "") -> dict:
    """Record a one-click 'send'. Returns the sent record. Demo only: nothing leaves."""
    global _seq
    _seq += 1
    rec = {
        "id": f"msg-{_seq:03d}",
        "lead_id": lead_id,
        "channel": channel,
        "subject": subject,
        "body": body,
        "to": to or ("in-app message" if channel == "in-app" else "(prospective patient)"),
        "status": "sent",
        "sent_at": datetime.now().isoformat(timespec="seconds"),
    }
    _persist(rec)
    return rec


def queue_message(recipient_id: str, channel: str, subject: str, body: str, to: str = "") -> dict:
    """Queue a drafted message for human review (status queued_for_review). It appears in the
    Outbox and is never auto-sent; a person approves before anything goes out."""
    global _seq
    _seq += 1
    rec = {
        "id": f"msg-{_seq:03d}", "lead_id": recipient_id, "channel": channel,
        "subject": subject, "body": body, "to": to or "(recipient)",
        "status": "queued_for_review",
        "sent_at": datetime.now().isoformat(timespec="seconds"),
    }
    _persist(rec)
    return rec


def list_outbox() -> list[dict]:
    fs = _outbox_fs()
    if fs:
        try:
            docs = [d.to_dict() for d in fs.collection(_OUTBOX_COLL).stream()]
            if docs:
                return sorted(docs, key=lambda r: r.get("sent_at", ""), reverse=True)
        except Exception:
            pass
    return list(reversed(_OUTBOX))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fs_set_sent(field: str, value: str) -> int:
    fs = _outbox_fs()
    if not fs:
        return 0
    n = 0
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        q = fs.collection(_OUTBOX_COLL).where(filter=FieldFilter(field, "==", value))
        for doc in q.stream():
            doc.reference.update({"status": "sent", "sent_at": _now()})
            n += 1
    except Exception:
        pass
    return n


def approve_message(msg_id: str) -> dict:
    """Approve a queued-for-review message: mark it sent (human-in-the-loop). Updates the
    in-instance copy and Firestore if configured."""
    for rec in _OUTBOX:
        if rec.get("id") == msg_id and rec.get("status") != "sent":
            rec["status"] = "sent"
            rec["sent_at"] = _now()
    _fs_set_sent("id", msg_id)
    return {"id": msg_id, "status": "sent"}


def approve_all() -> dict:
    """Approve every queued-for-review message at once."""
    n = 0
    for rec in _OUTBOX:
        if rec.get("status") == "queued_for_review":
            rec["status"] = "sent"
            rec["sent_at"] = _now()
            n += 1
    n += _fs_set_sent("status", "queued_for_review")
    return {"approved": n}


def discard_message(msg_id: str) -> dict:
    """Discard a queued draft without sending (the human rejected it)."""
    global _OUTBOX
    _OUTBOX = [r for r in _OUTBOX if r.get("id") != msg_id]
    fs = _outbox_fs()
    if fs:
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            for doc in fs.collection(_OUTBOX_COLL).where(filter=FieldFilter("id", "==", msg_id)).stream():
                doc.reference.delete()
        except Exception:
            pass
    return {"id": msg_id, "status": "discarded"}
