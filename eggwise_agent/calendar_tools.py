"""Calendar action tools: turn agent intent into real, ready-to-use calendar events.

No OAuth in the demo path. Each tool returns a working Google Calendar "add event"
link plus an iCalendar (.ics) body, so the action is genuinely usable by anyone who
clicks it, and stays human-in-the-loop: nothing is auto-sent. In production these map
to the clinic's existing Google Calendar OAuth integration in EggWise-Hippa.

All data is synthetic (Vance / Test Fertility Clinic Las Vegas).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import quote_plus

# Demo clinic timezone (Test Fertility Clinic Las Vegas).
_TZ = "America/Los_Angeles"
_CLINIC = "Test Fertility Clinic Las Vegas (or telehealth)"


def _parse(date: str, time: str) -> datetime:
    return datetime.strptime(f"{date.strip()} {time.strip()}", "%Y-%m-%d %H:%M")


def _basic(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def _gcal_link(title: str, start: datetime, end: datetime, details: str,
               location: str = "", recur: str = "") -> str:
    params = [
        "action=TEMPLATE",
        "text=" + quote_plus(title),
        f"dates={_basic(start)}/{_basic(end)}",
        "ctz=" + quote_plus(_TZ),
        "details=" + quote_plus(details),
    ]
    if location:
        params.append("location=" + quote_plus(location))
    if recur:
        params.append("recur=" + quote_plus(recur))
    return "https://calendar.google.com/calendar/render?" + "&".join(params)


def _ics(title: str, start: datetime, end: datetime, details: str,
         location: str = "", rrule: str = "") -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EggWise//Agent//EN",
        "BEGIN:VEVENT",
        f"SUMMARY:{title}",
        f"DTSTART:{_basic(start)}",
        f"DTEND:{_basic(end)}",
        f"DESCRIPTION:{details}",
    ]
    if location:
        lines.append(f"LOCATION:{location}")
    if rrule:
        lines.append(rrule)
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\n".join(lines)


def schedule_followup(patient_id: str, date: str, time: str = "09:00",
                      reason: str = "follow-up consultation",
                      duration_minutes: int = 30) -> dict:
    """Create a ready-to-send follow-up appointment invite for a clinician (Care).

    Args:
        patient_id: the patient's id.
        date: appointment date, YYYY-MM-DD.
        time: 24h start time, HH:MM (clinic timezone). Defaults to 09:00.
        reason: short reason for the follow-up.
        duration_minutes: appointment length in minutes.

    Human-in-the-loop: returns a Google Calendar link and an .ics body for the
    clinician to review and send. It does not auto-send or auto-book. In production
    this posts to the clinic Google Calendar via the existing OAuth integration.
    """
    try:
        start = _parse(date, time)
    except ValueError:
        return {"error": f"Could not parse '{date} {time}'. Use date YYYY-MM-DD and time HH:MM."}
    end = start + timedelta(minutes=int(duration_minutes))
    title = f"EggWise follow-up: {patient_id}"
    details = (f"Reason: {reason}. Drafted by the EggWise Agent for clinician review. "
               f"Patient: {patient_id}.")
    return {
        "patient_id": patient_id,
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "timezone": _TZ,
        "reason": reason,
        "status": "ready_for_clinician_to_send",
        "google_calendar_link": _gcal_link(title, start, end, details, _CLINIC),
        "ics": _ics(title, start, end, details, _CLINIC),
        "note": ("Human-in-the-loop: clinician confirms before sending. Production wires "
                 "this to the clinic Google Calendar via existing OAuth."),
    }


def reschedule_followup(patient_id: str, new_date: str, new_time: str = "09:00",
                        reason: str = "rescheduled follow-up",
                        duration_minutes: int = 30) -> dict:
    """Reschedule a patient's follow-up to a new date/time. Returns an updated
    calendar invite for review (same human-in-the-loop posture as scheduling)."""
    res = schedule_followup(patient_id, new_date, new_time, reason, duration_minutes)
    if "error" not in res:
        res["status"] = "rescheduled_ready_for_clinician_to_send"
    return res


def cancel_followup(patient_id: str, date: str, reason: str = "cancelled") -> dict:
    """Record a follow-up cancellation for a patient. Returns a cancellation record
    the front desk can confirm; does not send anything automatically."""
    return {
        "patient_id": patient_id,
        "date": date,
        "reason": reason,
        "status": "cancellation_ready_to_confirm",
        "note": "Front desk confirms the cancellation. Production updates the clinic calendar.",
    }


def set_medication_reminder(patient_id: str, medication: str, time: str = "20:00",
                            start_date: str = "", days: int = 14) -> dict:
    """Create a recurring daily medication reminder the patient can add to their
    calendar with one click (Companion).

    Args:
        patient_id: the patient's id.
        medication: the medication name (no dosage advice; a reminder only).
        time: 24h reminder time, HH:MM. Defaults to 20:00.
        start_date: first day YYYY-MM-DD. Defaults to today.
        days: number of days to repeat the daily reminder.

    Returns a Google Calendar link and .ics with a daily recurrence. This is a
    reminder only and never constitutes medical advice.
    """
    if not start_date.strip():
        start_date = datetime.now().strftime("%Y-%m-%d")
    try:
        start = _parse(start_date, time)
    except ValueError:
        return {"error": f"Could not parse '{start_date} {time}'. Use date YYYY-MM-DD and time HH:MM."}
    end = start + timedelta(minutes=15)
    title = f"EggWise reminder: {medication}"
    details = (f"Time to take {medication}. Reminder set with your EggWise companion. "
               f"This is a reminder only, not medical advice.")
    rrule = f"RRULE:FREQ=DAILY;COUNT={int(days)}"
    return {
        "patient_id": patient_id,
        "medication": medication,
        "time": time,
        "frequency": f"daily for {int(days)} days",
        "status": "ready_to_add",
        "google_calendar_link": _gcal_link(title, start, end, details, "", recur=rrule),
        "ics": _ics(title, start, end, details, "", rrule=rrule),
        "note": "A reminder only. Not medical advice.",
    }
