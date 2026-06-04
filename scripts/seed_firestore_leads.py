"""Seed the synthetic patient leads into Firestore (production-path proof).

Writes data/sample_patient_leads.json into the `patient_leads` collection so the
MCP lead server and the console can run against Firestore exactly as they would in
EggWise-Hippa. Synthetic, de-identified data only.

Usage:
    python scripts/seed_firestore_leads.py
Env:
    EGGWISE_LEADS_PROJECT     GCP project (default GOOGLE_CLOUD_PROJECT)
    EGGWISE_LEADS_COLLECTION  collection name (default "patient_leads")
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from google.cloud import firestore

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "sample_patient_leads.json"


def main() -> None:
    project = (os.environ.get("EGGWISE_LEADS_PROJECT")
               or os.environ.get("GOOGLE_CLOUD_PROJECT")
               or "eggwise-agent-challenge")
    collection = os.environ.get("EGGWISE_LEADS_COLLECTION", "patient_leads")

    with open(DATA, "r", encoding="utf-8") as f:
        leads = json.load(f)

    client = firestore.Client(project=project)
    col = client.collection(collection)
    for lead in leads:
        doc_id = lead.get("id")
        col.document(doc_id).set(lead)
        print(f"  wrote {doc_id}  ({lead.get('alias')})")
    print(f"Seeded {len(leads)} leads into {project}/{collection}.")


if __name__ == "__main__":
    main()
