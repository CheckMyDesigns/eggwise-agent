"""Offline test (no model call needed for the keyword path): simulate the history
the patient companion sees AFTER a coordinator transfer, and confirm the guardrail
still finds the medical text and blocks. Also checks a benign message passes."""
import asyncio

from google.adk.models import LlmRequest
from google.genai import types

from eggwise_agent.guardrails import _last_user_text, medical_safety_guardrail

# Post-transfer history: real user text, the coordinator's transfer call, then a
# function-response message that ALSO has role="user" but no text.
medical = LlmRequest(contents=[
    types.Content(role="user", parts=[types.Part(text="I have sharp pelvic pain, should i change my dose?")]),
    types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="transfer_to_agent", args={"agent_name": "patient_companion_agent"}))]),
    types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(name="transfer_to_agent", response={"result": "ok"}))]),
])
benign = LlmRequest(contents=[
    types.Content(role="user", parts=[types.Part(text="can you book my follow-up please")]),
])


async def main():
    text = _last_user_text(medical)
    verdict = await medical_safety_guardrail(None, medical)
    print("last_user_text :", repr(text))
    print("medical blocked:", type(verdict).__name__ if verdict else "None (FAIL)")
    ben = await medical_safety_guardrail(None, benign)
    print("benign passed  :", "None (OK)" if ben is None else "BLOCKED (FAIL)")


if __name__ == "__main__":
    asyncio.run(main())
