"""Website address and local storage paths. The token stays in the environment."""

import os
from pathlib import Path

BASE = os.getenv(
    "CRM_BASE", "https://analyst-assessment-production.up.railway.app"
).rstrip("/")
ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv("BELLHAVEN_DATA", str(ROOT / "data")))
DATA.mkdir(parents=True, exist_ok=True)
