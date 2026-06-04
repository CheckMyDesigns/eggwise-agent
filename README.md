# EggWise Agent (Google for Startups AI Agents Challenge, Track 1)

An autonomous, multi-agent system built with Google's Agent Development Kit (ADK),
Gemini, and the Model Context Protocol (MCP). It is the AI layer inside EggWise-Hippa,
a deployed, HIPAA-oriented fertility platform, and runs on Cloud Run.

## Live demo
A login-gated instance runs on Cloud Run:
**https://eggwise-agent-hdakio4noa-uc.a.run.app**
(credentials are provided with the challenge submission). All data is synthetic and
de-identified, so nothing touches a real patient.

After signing in you land on the **EggWise Agent front-desk console**: a branded UI that
does what a clinic front desk does. Find and rank prospective patients by fit, draft a
personalized, consent-safe outreach message and send it with one click, schedule
follow-ups and medication reminders (with real add-to-calendar links), open a patient for
an adherence and symptom report with clinician-review flags, and a command bar that drives
the live multi-agent coordinator in natural language. The raw ADK developer chat stays
available at `/dev-ui/`.

## What it does
One coordinator routes every request to three specialists:
- **Growth** (for clinics): patient lead generation. Finds prospective patients and
  their Wellness Scores over MCP, ranks them by fit for the clinic, gives a one-line
  reason why the clinic is the best match for each, and drafts a personalized, PHI-free
  first-contact message (email or in-app) for one-click sending. Clinical detail (AMH,
  BMI, diagnosis) is shown only for patients who consented to share.
- **EggWise Agent** (for clinicians): reviews a patient's logs, generates a structured
  health report (adherence, symptom trend, mood, risk flags), flags at-risk patients, and
  drafts check-ins plus calendar follow-up invites for clinician review.
- **Companion** (for patients): medication reminders (with add-to-calendar links),
  booking follow-ups, logistics, and encouragement. It never gives medical advice and
  escalates clinical questions.

Think of it as Ask versus Agent: "Ask EggWise" answers questions, EggWise Agent acts.

## Architecture
```
eggwise_coordinator              (root, routes every request via LLM-driven delegation)
  |-- growth_agent                patient lead-gen; tools over MCP (mcp_leads_server.py)
  |-- care_agent                  EggWise Agent: clinician assistant
  |-- patient_companion_agent     patient-facing help + medical-safety guardrail
```
It runs inside **EggWise-Hippa**: in production it reuses the platform's Firebase Auth,
consent model, and least-privilege access, is gated by Stripe entitlements, and reads
platform data (logs, leads, consent) from Firestore read-only.

## Safety (by design)
- Companion never gives medical advice. Three layers enforce it:
  1. Instruction: escalate any clinical question via `escalate_to_care_team`.
  2. `before_model_callback` guardrail: a fast keyword filter plus an LLM safety
     classifier block the model on clinical content and return a safe escalation. It
     degrades to the keyword decision if the classifier call fails. See
     `eggwise_agent/guardrails.py`.
  3. Audit trail: every block is logged to `logs/audit.jsonl`, so escalations are never
     silent.
- Growth leads are de-identified until the clinic engages; clinical fields are
  consent-gated via `consented_to_share`.
- Human-in-the-loop on anything outbound or patient-facing.
- All demo data is synthetic (Vance / Test Fertility Clinic Las Vegas). Nothing touches
  real patients.

## Evaluated
`python evals.py` runs a 10-scenario suite. Latest result: **100% routing accuracy,
100% guardrail catch** on clinical questions, and 0 false blocks on benign requests.

## Run it locally
```powershell
# 1. Authenticate ADC (opens a browser; rerun if you see a RefreshError)
gcloud auth application-default login
gcloud auth application-default set-quota-project eggwise-agent-challenge

# 2. Activate the venv and launch the dev UI
.\.venv\Scripts\Activate.ps1
adk web --reload_agents .
```
Pick `eggwise_agent` and try:
- "Find prospective patients for my San Francisco fertility clinic"   (Growth, over MCP)
- "As a clinician, review pt-jasmine's logs and draft a check-in"      (EggWise Agent)
- "I'm pt-jasmine, how am I doing on my meds?"                         (Companion)
- "I'm pt-sarah, I have pelvic pain, should I change my dose?"         (guardrail escalates)

Or run the scenarios headless: `python run_scenarios.py`. Gemini auth is read from
`eggwise_agent/.env` (Vertex AI); copy `.env.example` to start.

## Configuration (env vars)
Lead data backend (read by `mcp_leads_server.py`):
- `EGGWISE_LEADS_BACKEND` = `json` (default, synthetic) or `firestore`
- `EGGWISE_LEADS_PROJECT` = GCP project for Firestore (e.g. `eggwise-hippa`)
- `EGGWISE_LEADS_COLLECTION` = Firestore collection (default `patient_leads`)

MCP transport: `EGGWISE_MCP_TRANSPORT` = `stdio` (default), `http`, or `sse`
(`EGGWISE_MCP_HOST`, `EGGWISE_MCP_PORT`).

## Deploy
See `DEPLOY.md`. In short, from this folder:
`gcloud run deploy eggwise-agent --source . --region us-central1 ...`. The Dockerfile
packages the agent, the MCP server, and the data, and serves the ADK FastAPI app through
`main.py`, which adds a signed-cookie login gate (`DEMO_USER` / `DEMO_PASS`) in front of
the console.

## Project layout
```
eggwise_agent/
  agent.py                    root coordinator (root_agent), 3 sub-agents
  growth_agent.py             Growth (patient lead-gen); tools via MCPToolset
  care_agent.py               EggWise Agent (clinician assistant)
  patient_companion_agent.py  Companion + medical-safety guardrail
  guardrails.py               keyword + LLM-classifier before_model_callback
  audit.py                    append-only audit trail
  tools.py                    clinician/Care tool functions (synthetic)
  patient_tools.py            patient-facing tool functions
mcp_leads_server.py           standalone MCP server (JSON / Firestore backend; stdio / HTTP)
data/                         synthetic patient leads, patient logs, approved content
evals.py                      eval suite (routing, guardrail, benign)
run_scenarios.py              multi-scenario tester
Dockerfile                    Cloud Run image
```

## Roadmap
- [x] Multi-agent coordinator with three specialists
- [x] Growth = patient lead-gen with consent-gated clinical detail
- [x] Lead outreach: personalized, PHI-free draft + one-click send (simulated outbox)
- [x] Scheduling and medication reminders with real add-to-calendar links
- [x] Patient health reports (adherence, symptom trend, mood, risk flags)
- [x] Branded front-desk console UI + command bar over the live coordinator
- [x] MCP server (JSON / Firestore backend, stdio / HTTP)
- [x] Layered medical-safety guardrail + audit trail
- [x] Eval suite (100% routing, 100% guardrail catch)
- [x] Deployed on Cloud Run behind a login gate
- [~] Firestore backend ready; enable with env vars + a read-only credential
- [ ] 3-minute demo video
- [ ] Full integration into the EggWise-Hippa app (Stripe entitlements gating)

Submission deadline: 2026-06-11.
