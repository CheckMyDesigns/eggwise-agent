"""Lightweight append-only audit trail.

Every safety-relevant action (a guardrail block, an escalation) is recorded so
there is a reviewable record. This is the technical foundation for compliance and
for the human-in-the-loop story. Data-minimized: we store what happened and a
source, not raw patient message text.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_LOG = Path(__file__).resolve().parent.parent / "logs" / "audit.jsonl"


def record(actor: str, action: str, details: Optional[dict] = None) -> dict:
    """Append one audit entry and return it."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "details": details or {},
    }
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry
