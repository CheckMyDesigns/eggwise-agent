"""Growth sub-agent: lead generation FOR fertility doctors and clinics.

Growth helps a clinic find prospective patients (suspected leads). It pulls
prospective patients and their Wellness Scores over a standalone MCP server
(mcp_leads_server.py), ranks them by fit for the clinic, and gives a one-line
reason why the clinic is the best match for each patient. Prospective patients are
de-identified until the clinic engages.
"""
import os
import sys
from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import MCPToolset, StdioConnectionParams
from mcp import StdioServerParameters

MODEL = "gemini-2.5-flash"

_MCP_SERVER = str(Path(__file__).resolve().parent.parent / "mcp_leads_server.py")

# Patient-lead tools come over MCP from a separate process, not in-process functions.
leads_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[_MCP_SERVER],
            env=dict(os.environ),  # forward EGGWISE_* + Vertex config to the server
        ),
        timeout=30,
    )
)

growth_agent = Agent(
    name="growth_agent",
    model=MODEL,
    description=(
        "Patient lead generation for fertility doctors and clinics. Finds prospective "
        "patients (suspected leads), ranks them by Wellness Score and fit, and explains "
        "in one line why this clinic is the best match for each patient. Route here for "
        "finding patients, lead gen, growing the practice, or the Premium Leads marketplace."
    ),
    instruction=(
        "You are the EggWise Growth agent: lead generation that helps a fertility doctor "
        "or clinic find prospective patients who fit their practice.\n\n"
        "Process:\n"
        "1. Call list_patient_leads to see prospective patients and their Wellness Scores.\n"
        "2. Rank them by fit for the clinic: a higher Wellness Score (more engaged and "
        "ready), a location near the clinic, and a goal that matches the clinic's "
        "specialty (for example egg freezing or IVF).\n"
        "3. For each top prospective patient, write ONE line on why this clinic is the "
        "best fit for that patient, referencing the score, location, and goal.\n"
        "4. Call save_match for each patient the clinic should pursue.\n\n"
        "If the clinic's specialty and location are not given, ask for them first.\n"
        "Consent rule: for a lead with consented_to_share = true, you MAY use and mention its "
        "clinical details (AMH, BMI, prior treatment, diagnosis) in the fit reasoning. For a "
        "lead with consented_to_share = false, do NOT reveal or use clinical details: show only "
        "the de-identified teaser (initials, age, location, goal, Wellness Score) and note that "
        "the full clinical profile unlocks once the patient consents.\n"
        "Never invent patient details. The clinic reviews and approves any outreach. Present a "
        "ranked summary at the end, then close with this exact line on its own:\n"
        "This data is from the EggWise AI Fertility Tracker."
    ),
    tools=[leads_toolset],
)
