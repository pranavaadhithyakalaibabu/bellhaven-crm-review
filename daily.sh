#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# For cron, place CRM_TOKEN=... in a chmod 600 file outside this project.
if [[ -n "${BELLHAVEN_ENV_FILE:-}" ]]; then
  set -a
  source "$BELLHAVEN_ENV_FILE"
  set +a
fi
: "${CRM_TOKEN:?Set CRM_TOKEN or BELLHAVEN_ENV_FILE}"
exec python3 reconcile.py
