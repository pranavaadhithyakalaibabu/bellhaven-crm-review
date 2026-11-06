"""Shared page layout and escaping."""

import html
from pathlib import Path

STYLE = Path(__file__).with_name("style.css").read_text()
STATUS_LABELS = {
    "pending": "Waiting for review",
    "applied": "Approved & completed",
    "rejected": "Rejected",
    "approved": "Approved, needs attention",
    "superseded": "No longer needed",
    "all": "All decisions",
}
STATUS_HELP = {
    "pending": "Choose Approve or Reject.",
    "applied": "Approved changes saved to the CRM.",
    "rejected": "Declined; no proposed change written.",
    "approved": "Check ownership, a possible duplicate, or a difference in the live CRM.",
}
NAV = (
    "<nav>"
    + "".join(
        '<a href="' + url + '">' + html.escape(label) + "</a>"
        for url, label in [
            ("/?state=pending", STATUS_LABELS["pending"]),
            ("/?state=applied", STATUS_LABELS["applied"]),
            ("/?state=rejected", STATUS_LABELS["rejected"]),
            ("/?state=approved", STATUS_LABELS["approved"]),
            ("/?state=all", "All decisions"),
            ("/matches", "All locations"),
        ]
    )
    + "</nav>"
)


def esc(value):
    return html.escape(str(value if value is not None else "—"), quote=True)


def crm_link(account_id):
    return "/crm/" + account_id


def layout(body):
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bellhaven · Ownership review</title><style>{STYLE}</style></head>
<body><header><small>BELLHAVEN / DATA OPERATIONS</small><h1>Ownership review</h1>
<div>Every write requires a recorded decision.</div></header>
<main>{body}</main></body></html>"""
