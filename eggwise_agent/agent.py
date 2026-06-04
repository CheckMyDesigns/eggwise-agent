"""Root coordinator agent for the EggWise multi-agent system.

Architecture (Google for Startups AI Agents Challenge, Track 1):

    eggwise_coordinator        (root, routes requests)
      |-- growth_agent          clinic lead qualification (B2B)
      |-- care_agent            clinician copilot (reviews patients, drafts for clinician)
      |-- patient_companion_agent   patient-facing help (reminders, booking, escalation)

One coordinator dividing into three specialists. The coordinator does no work
itself; it routes each request via ADK's LLM-driven delegation, which is the
multi-agent pattern judges reward over a single chatbot.
"""
from google.adk.agents import Agent

from .care_agent import care_agent
from .growth_agent import growth_agent
from .patient_companion_agent import patient_companion_agent

MODEL = "gemini-2.5-flash"

root_agent = Agent(
    name="eggwise_coordinator",
    model=MODEL,
    description="EggWise platform coordinator that routes work to the Growth, Care, and Patient Companion agents.",
    instruction=(
        "You are the EggWise coordinator. Route each request to the right specialist "
        "and do not do the work yourself.\n"
        "- Lead qualification, sales, clinic growth, the Premium Leads marketplace: "
        "transfer to growth_agent.\n"
        "- A CLINICIAN reviewing patients, daily logs, or drafting clinician notes and "
        "reports: transfer to care_agent.\n"
        "- A PATIENT asking for help for themselves (medication reminders, booking a "
        "follow-up, prep or logistics questions, encouragement): transfer to "
        "patient_companion_agent.\n"
        "If you cannot tell whether the speaker is a clinician or a patient, ask. "
        "Briefly tell the user which specialist you are handing to and why."
    ),
    sub_agents=[growth_agent, care_agent, patient_companion_agent],
)
