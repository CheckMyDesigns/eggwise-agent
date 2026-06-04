"""Central configuration for the EggWise agent (env-overridable).

Keeping the clinic identity and model in one place makes the system production-ready:
a deployment points at its own clinic and model without code changes.
"""
import os

# Smartest available default; flip to gemini-2.5-pro via env for deeper reasoning.
MODEL = os.environ.get("EGGWISE_MODEL", "gemini-2.5-flash")

CLINIC_NAME = os.environ.get("EGGWISE_CLINIC", "Test Fertility Clinic Las Vegas")
CLINIC_LOCATION = os.environ.get("EGGWISE_CLINIC_LOCATION", "Las Vegas, NV")
CLINIC_SPECIALTY = os.environ.get("EGGWISE_CLINIC_SPECIALTY", "egg freezing and IVF")
