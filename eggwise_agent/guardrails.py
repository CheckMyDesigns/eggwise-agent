"""Safety guardrails for patient-facing agents (defense-in-depth).

The patient companion's instruction already forbids medical advice. This callback
adds two more layers and an audit record:

  1. A fast keyword pre-filter blocks obvious clinical messages with no model call.
  2. For anything not obviously benign, an LLM safety classifier decides whether
     the message needs a clinician, catching phrasings the keywords miss.
  3. Every block is written to the audit trail, so escalations are never silent.

If the classifier errors (for example, expired credentials), the keyword decision
still stands and the agent's own escalate instruction remains as a final backstop,
so the guardrail degrades safely rather than crashing the agent.
"""
from __future__ import annotations

import re
from typing import Optional

from google import genai
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

from . import audit

# Layer 1: obvious clinical content -> block immediately, no model call.
_MEDICAL_PATTERNS = [
    r"\bpain\b", r"\bbleed", r"\bcramp", r"\bnause", r"\bdizz", r"\bfever\b",
    r"\bsymptom", r"\bside effect", r"\bdose\b", r"\bdosage\b", r"\bmilligram",
    r"\bis (this|it|that) (normal|safe|okay|ok)\b",
    r"\bshould i (take|stop|change|increase|decrease)\b",
    r"\bswell", r"\bspotting\b", r"\brash\b", r"\bclot",
    r"\bovar(y|ies)\b", r"\binfection\b", r"\ballerg",
]

# Clearly in-scope, non-clinical intents -> allow without an LLM classifier call.
_BENIGN_PATTERNS = [
    r"\bbook\b", r"\bschedul", r"\bremind", r"\bappointment\b", r"\bfollow.?up\b",
    r"\bhow am i doing\b", r"\bthank", r"\bhello\b", r"^\s*hi\b",
    r"\bhow do i log\b", r"\bwhat (do i|should i) bring\b", r"\bhours\b",
    r"\bmotivat", r"\bstreak\b",
]

_SAFE_REPLY = (
    "I'm not able to give medical advice. I've flagged this for your care team, and "
    "they will follow up with you. If this feels urgent, please call your clinic or "
    "emergency services right away."
)

_CLASSIFIER_MODEL = "gemini-2.5-flash"
_CLASSIFIER_PROMPT = (
    "You are a safety classifier for a fertility patient app. A patient companion may "
    "help with reminders, scheduling, logistics, and encouragement, but must NEVER give "
    "medical advice or interpret symptoms. Reply with exactly YES if the patient message "
    "asks for medical advice, describes symptoms, or needs a clinician; otherwise reply "
    "NO.\n\nMessage: "
)

_client: Optional["genai.Client"] = None


def _genai_client() -> "genai.Client":
    global _client
    if _client is None:
        _client = genai.Client()  # reads Vertex config from env
    return _client


def _last_user_text(llm_request: LlmRequest) -> str:
    # Scan newest-first to the most recent real user utterance. After an agent
    # transfer the history ends with a function-response message that also has
    # role="user" but no text, so skip text-less user messages.
    for content in reversed(getattr(llm_request, "contents", None) or []):
        if getattr(content, "role", None) != "user" or not content.parts:
            continue
        text = " ".join(p.text for p in content.parts if getattr(p, "text", None))
        if text.strip():
            return text.lower()
    return ""


def _keyword_medical(text: str) -> bool:
    return any(re.search(p, text) for p in _MEDICAL_PATTERNS)


def _looks_benign(text: str) -> bool:
    return any(re.search(p, text) for p in _BENIGN_PATTERNS)


async def _llm_says_medical(text: str) -> bool:
    try:
        resp = await _genai_client().aio.models.generate_content(
            model=_CLASSIFIER_MODEL, contents=_CLASSIFIER_PROMPT + text
        )
        return (resp.text or "").strip().upper().startswith("YES")
    except Exception as exc:  # never crash the agent on a classifier failure
        audit.record("guardrail", "classifier_error", {"error": type(exc).__name__})
        return False


async def medical_safety_guardrail(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """Block medical-advice requests before they reach the model."""
    text = _last_user_text(llm_request)
    if not text:
        return None

    source = None
    if _keyword_medical(text):
        source = "keyword"
    elif not _looks_benign(text) and await _llm_says_medical(text):
        source = "llm_classifier"

    if source:
        audit.record(
            "patient_companion_agent",
            "medical_safety_block",
            {"source": source, "chars": len(text)},
        )
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=_SAFE_REPLY)])
        )
    return None
