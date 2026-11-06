"""Small helpers for timestamps, JSON and stable proposal IDs."""

import datetime
import hashlib
import json


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False))
