"""Authenticated CRM reads and writes. Only reads are retried automatically."""

import os
import json
import time
import urllib.request
import urllib.error
import settings
from common import encode


def request(path, method="GET", body=None):
    """Send an authenticated request. Retry reads, never uncertain writes."""
    token = os.environ.get("CRM_TOKEN")
    if not token:
        raise RuntimeError("Set CRM_TOKEN in the environment.")
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Only same-origin paths allowed")
    http_request = urllib.request.Request(
        settings.BASE + path,
        data=None if body is None else encode(body).encode(),
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "BellhavenReconciler/1.0",
        },
    )
    for attempt in range(3 if method == "GET" else 1):
        try:
            with urllib.request.urlopen(http_request, timeout=40) as response:
                if not response.url.startswith(settings.BASE + "/"):
                    raise RuntimeError("Unexpected redirect")
                raw = response.read().decode()
                return json.loads(raw) if "/api/" in path else raw
        except (urllib.error.URLError, TimeoutError):
            if method != "GET" or attempt == 2:
                raise
            time.sleep(2**attempt)


def all_records(entity):
    """Read every page and stop if the CRM changes during pagination."""
    result = []
    page = 1
    total = None
    while True:
        page_result = request(f"/api/v1/{entity}?page={page}&page_size=100")
        if total is None:
            total = page_result["total"]
        if page_result["total"] != total:
            raise RuntimeError("CRM changed during pagination; rerun")
        result.extend(page_result["data"])
        if len(result) >= total:
            break
        if not page_result["data"]:
            raise RuntimeError("Incomplete pagination")
        page += 1
    ids = [record[entity[:-1] + "_id"] for record in result]
    if len(result) != total or len(set(ids)) != total:
        raise RuntimeError("Duplicate or missing API page")
    return result


def account(account_id):
    response = request("/api/v1/accounts/" + account_id)
    return response.get("data", response)


def validate_before(before, current):
    """Stop if a business field changed after the reviewer snapshot."""
    for key in before:
        if key not in ("updated_at", "parent_name") and before[key] != current.get(key):
            raise RuntimeError(
                "CRM changed since review snapshot: "
                + key
                + ". Rerun pipeline before approving."
            )
