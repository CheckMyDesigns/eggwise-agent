"""End-to-end smoke test: run the coordinator and watch it route and use tools.

Run with Vertex env vars set (GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT,
GOOGLE_CLOUD_LOCATION) and PYTHONPATH including this folder:

    python smoke_agent.py
"""
import asyncio
import sys

from google.adk.runners import InMemoryRunner
from google.genai import types

from eggwise_agent.agent import root_agent

PROMPT = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "Qualify our inbound leads and give me the top 2 with a one-line reason each."
)


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="eggwise")
    session = await runner.session_service.create_session(app_name="eggwise", user_id="demo")
    message = types.Content(role="user", parts=[types.Part(text=PROMPT)])

    async for event in runner.run_async(
        user_id="demo", session_id=session.id, new_message=message
    ):
        author = getattr(event, "author", "?")
        if not (event.content and event.content.parts):
            continue
        for part in event.content.parts:
            if getattr(part, "function_call", None):
                print(f"[{author}] -> tool/route: {part.function_call.name}")
            if getattr(part, "text", None) and part.text.strip():
                print(f"[{author}] {part.text.strip()}")


if __name__ == "__main__":
    asyncio.run(main())
