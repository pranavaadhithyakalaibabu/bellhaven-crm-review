"""Show one proposal, its evidence and the review controls."""

import json
from ui.layout import NAV, esc, crm_link, STATUS_LABELS
from ui.explanations import ACTION_LABELS, FIELD_LABELS, explanation


def proposal_page(row, csrf, confirmation=None, category=None, live_panel=""):
    proposal_id = row["id"]
    proposal = json.loads(row["payload"])
    account_record = proposal["before"] or {}
    location = proposal["location"]
    body = (
        NAV
        + '<section><span class="tag">'
        + esc(ACTION_LABELS.get(proposal["kind"], proposal["kind"]))
        + " · "
        + esc(STATUS_LABELS.get(category or row["state"], row["state"]))
        + "</span><h1>"
        + esc(proposal["title"])
        + "</h1><p>"
        + esc(explanation(proposal, row["state"], confirmation))
        + "</p>"
    )
    body += live_panel
    if location:
        body += (
            '<p><a target="_blank" rel="noreferrer" href="'
            + esc(location["source_url"])
            + '">Website evidence ↗</a> · '
            + esc(
                location["billing_street"]
                + ", "
                + location["billing_city"]
                + ", "
                + location["billing_state"]
                + " "
                + location["billing_zip"]
            )
            + "</p><p>Care offerings: "
            + esc(", ".join(location["care_offerings"]))
            + "</p>"
        )
    if account_record:
        body += (
            '<p><a target="_blank" rel="noreferrer" href="'
            + crm_link(account_record["account_id"])
            + '">Open CRM account ↗</a> · '
            + esc(account_record.get("parent_name") or "No parent")
            + "</p>"
        )
    body += (
        '<div class="grid"><div><h3>Billing check</h3><p>Total past revenue: $'
        + esc(account_record.get("lifetime_revenue", 0))
        + "<br>Unpaid balance: $"
        + esc(account_record.get("outstanding_ar", 0))
        + "</p></div><div><h3>Review details</h3><small>"
        + esc(proposal["id"])
        + "<br>Saved on: "
        + esc(row["created_at"])
        + "</small></div></div>"
    )
    if proposal["kind"] == "chow":
        body += '<p class="warning"><b>Billing rule:</b> keep the old account unchanged except for a link to the new account. Do not move its unpaid bills or change its parent.</p>'
    if proposal["kind"] == "absent":
        body += '<p class="warning">Missing from the website does not prove the facility was sold or closed.</p>'
    if account_record.get("billing_street", "").lower().startswith("po box"):
        body += '<p class="warning">A billing PO box can be valid even when the website lists a street address.</p>'
    body += (
        "<p>These details were saved during the review. Open the CRM link to see the account now.</p>"
        "<table><tr><th>Field</th><th>Before change (saved)</th><th>"
        + ("Approved change" if row["state"] == "applied" else "Proposed change")
        + (" on NEW account" if proposal["kind"] == "chow" else "")
        + "</th></tr>"
    )
    for k, v in proposal["changes"].items():
        body += (
            "<tr><td>"
            + esc(FIELD_LABELS.get(k, k.replace("_", " ")))
            + "</td><td>"
            + esc(account_record.get(k))
            + "</td><td>"
            + esc(v)
            + "</td></tr>"
        )
    body += "</table>"
    if proposal["related"]:
        body += (
            "<details><summary>Other accounts considered ("
            + str(len(proposal["related"]))
            + ")</summary><pre>"
            + esc(json.dumps(proposal["related"], indent=2))
            + "</pre></details>"
        )
    body += (
        "<details><summary>Original matching explanation</summary><p>"
        + esc(proposal["reason"])
        + "</p></details>"
    )
    if row["error"]:
        body += '<p class="warning">' + esc(row["error"]) + "</p>"
    if row["state"] in ("pending", "approved"):
        body += (
            '<form method="post" action="/decide"><input type="hidden" name="csrf" value="'
            + csrf
            + '"><input type="hidden" name="id" value="'
            + esc(proposal_id)
            + '"><label>Reviewer<input name="reviewer" required placeholder="Your name"></label><label>Decision rationale<textarea name="reason" required placeholder="What evidence supports your decision?"></textarea></label><button name="decision" value="approve">'
            + (
                "Resume approved write"
                if row["state"] == "approved"
                else "Approve and write to CRM"
            )
            + "</button>"
        )
        if row["state"] == "pending":
            body += '<button class="reject" name="decision" value="reject">Reject proposal</button>'
        body += "</form>"
    else:
        if confirmation:
            body += (
                "<p><b>Checked after the change by "
                + esc(confirmation["reviewer"])
                + "</b> · "
                + esc(confirmation["confirmed_at"])
                + "</p>"
                + "<details><summary>Saved review note</summary>"
                + esc(confirmation["reason"])
                + "</details>"
                "<p>This later check did not change the CRM again.</p>"
            )
            body += "<details><summary>Original decision</summary>"
        body += (
            "<p><b>"
            + esc(STATUS_LABELS.get(row["state"], row["state"]))
            + "</b> by "
            + esc(row["reviewer"])
            + " · "
            + esc(row["decided_at"])
            + "</p><p>"
            + esc(row["reason"])
            + "</p>"
        )
        if confirmation:
            body += "</details>"
        if row["result"]:
            result = json.loads(row["result"])
            body += (
                '<a target="_blank" href="'
                + crm_link(result["account_id"])
                + '">Open current account in CRM ↗</a><details><summary>Saved CRM response</summary><pre>'
                + esc(json.dumps(result, indent=2))
                + "</pre></details>"
            )
    return body + "</section>"
