# EggWise Agent on Cloud Run.
# Packages the ADK agent, the MCP lead server, and the demo data into one image
# so the Growth agent's MCP (stdio) keeps working in the container.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE \
    GOOGLE_CLOUD_PROJECT=eggwise-agent-challenge \
    GOOGLE_CLOUD_LOCATION=us-central1 \
    ADK_DISABLE_LOCAL_STORAGE=1


WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY eggwise_agent ./eggwise_agent
COPY mcp_leads_server.py ./
COPY data ./data

# Cloud Run injects $PORT (default 8080). adk web falls back to in-memory
# sessions when the agents dir is read-only, which is the Cloud Run case.
CMD ["sh", "-c", "adk web --host 0.0.0.0 --port ${PORT:-8080} /app"]
