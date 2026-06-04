# Deploy EggWise Agent to Cloud Run

Run these from `agent-challenge/` in your own terminal (needs your gcloud auth).
APIs are already enabled (run, cloudbuild, artifactregistry).

## 1. Point at the challenge project
```powershell
gcloud config set project eggwise-agent-challenge
```

## 2. Let the Cloud Run service account call Gemini (Vertex AI)
The container authenticates as the Cloud Run runtime service account, so it needs
the Vertex AI User role.
```powershell
$PROJ = "eggwise-agent-challenge"
$NUM = gcloud projects describe $PROJ --format="value(projectNumber)"
gcloud projects add-iam-policy-binding $PROJ --member="serviceAccount:$NUM-compute@developer.gserviceaccount.com" --role="roles/aiplatform.user"
```

## 3. Deploy (Cloud Build builds the Dockerfile, then deploys)
```powershell
gcloud run deploy eggwise-agent --source . --region us-central1 --allow-unauthenticated --memory 1Gi --timeout 600 --set-env-vars GOOGLE_CLOUD_PROJECT=eggwise-agent-challenge,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_LOCATION=us-central1
```
- First run asks to create an Artifact Registry repo (`cloud-run-source-deploy`). Answer **Y**.
- It prints a **Service URL**. Open it, pick `eggwise_agent`, and try:
  - "Qualify our inbound leads and rank them"
  - "Review pt-jasmine's logs and draft a check-in"
  - "I'm pt-sarah, I have pelvic pain, what should I do?" (guardrail should escalate)

## Notes
- `--allow-unauthenticated` makes the URL public for the demo and judges. If an org
  policy blocks it, deploy without that flag and grant specific users the
  `roles/run.invoker` role instead.
- Sessions are in-memory on Cloud Run (fine for the demo). For persistence, redeploy
  with `--set-env-vars ... ADK_*` or pass `--session_service_uri` in the CMD.
- Logs: `gcloud run services logs read eggwise-agent --region us-central1`.
- Redeploy after code changes: rerun step 3.
