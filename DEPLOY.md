# Deploy EggWise Agent to Cloud Run

Run from `agent-challenge/` in your own terminal (needs your gcloud auth). The
Dockerfile bakes in the Vertex config, so you do not pass `--set-env-vars` for that.

## 1. Point at the challenge project
```powershell
gcloud config set project eggwise-agent-challenge
```

## 2. Grant the runtime service account the roles it needs
The container runs as the Cloud Run runtime service account (the project's compute SA).
```powershell
$PROJ = "eggwise-agent-challenge"
$SA = (gcloud projects describe $PROJ --format="value(projectNumber)") + "-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJ --member="serviceAccount:$SA" --role="roles/aiplatform.user"
# Only if using the Firestore backend (live leads + durable outbox):
gcloud projects add-iam-policy-binding $PROJ --member="serviceAccount:$SA" --role="roles/datastore.user"
```

## 3. Deploy (Cloud Build builds the Dockerfile, then deploys)
```powershell
gcloud run deploy eggwise-agent --source . --region us-central1
```
This preserves existing env vars. On the first deploy, answer **Y** to create the
Artifact Registry repo. It prints a **Service URL**.

## 4. Turn on the login gate (judges sign in)
The app is open until `DEMO_PASS` is set; once set, every route except `/login`,
`/logout`, `/healthz` requires a signed-cookie session.
```powershell
gcloud run services update eggwise-agent --region us-central1 --update-env-vars "DEMO_USER=judge"
gcloud run services update eggwise-agent --region us-central1 --update-env-vars "DEMO_PASS=YourAlphanumericPass"
```
Use an alphanumeric password (no commas/spaces, which break the flag).

## 5. Make it reachable by judges (public, behind the login gate)
If a Domain Restricted Sharing org policy blocks `allUsers`, lift it for this project,
then grant public invoke (the login gate still controls who gets in):
```powershell
gcloud resource-manager org-policies allow iam.allowedPolicyMemberDomains --project=eggwise-agent-challenge  # or set allValues=ALLOW
gcloud run services add-iam-policy-binding eggwise-agent --region=us-central1 --member=allUsers --role=roles/run.invoker
```

## What judges see
- Sign in at the service URL, land on **Ask EggWise**.
- **Clinic** view: Ask EggWise, Leads, Patients (triage + reports), Campaigns (batch
  personalized check-ins / outreach), Schedule, Outbox (queued -> approve & send).
- **Patient** view (Clinic/Patient switch): Ask EggWise, Dashboard, Reminders, Learn.
- The raw ADK developer UI stays at `/dev-ui/`.

## Optional: live Firestore backend + seed
```powershell
gcloud services enable firestore.googleapis.com --project eggwise-agent-challenge
gcloud firestore databases create --location=nam5 --project eggwise-agent-challenge
$env:EGGWISE_LEADS_PROJECT="eggwise-agent-challenge"; python scripts/seed_firestore_leads.py
gcloud run services update eggwise-agent --region us-central1 --update-env-vars "EGGWISE_LEADS_BACKEND=firestore,EGGWISE_LEADS_PROJECT=eggwise-agent-challenge"
```

## Notes
- Smartness: set `EGGWISE_MODEL=gemini-2.5-pro` to trade latency for deeper reasoning.
- Sessions are in-memory (fine for the demo); the outbox persists to Firestore when the
  Firestore backend is on, otherwise in-memory.
- Logs: `gcloud run services logs read eggwise-agent --region us-central1`.
- Redeploy after code changes: rerun step 3 (env vars are preserved).
