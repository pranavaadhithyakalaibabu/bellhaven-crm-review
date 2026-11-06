#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -z "${CRM_TOKEN:-}" ]]; then
  read -r -s -p 'CRM API token: ' CRM_TOKEN
  echo
  export CRM_TOKEN
fi
exec python3 app.py
