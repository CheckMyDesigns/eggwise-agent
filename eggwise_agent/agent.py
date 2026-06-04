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
from .config import MODEL
from .growth_agent import growth_agent
from .patient_companion_agent import patient_companion_agent

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
        "A line beginning with 'SESSION CONTEXT' may tell you whether you are talking to "
        "clinic staff or a patient, and may give a patient id. Trust it and route "
        "accordingly without re-asking. Only ask the user to clarify when there is no "
        "context AND the request is genuinely ambiguous. Never loop: prefer routing and "
        "acting with sensible defaults over asking follow-up questions. Briefly say which "
        "specialist is taking over."
    ),
    sub_agents=[growth_agent, care_agent, patient_companion_agent],
)
