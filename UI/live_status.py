"""Display categories are separate from approval and write recovery states."""
import json

from ui.layout import esc, crm_link

UNCERTAIN = {"Bellhaven Gardens of Monroe", "Bellhaven of Kettering"}


def classify(row, accounts):
    state = row["state"]
    p = json.loads(row["payload"])
    if state == "rejected":
        if row["id"] == "f0a2fe4c6ee0e971354812b2":
            return state, "Kept PO Box 517. The website lists the building at 3156 W Prospect Rd. Ask billing before changing where invoices go."
        return state, row["reason"] or "Review the saved decision."
    if state == "pending":
        return state, "Compare the website and CRM, then approve or reject the proposal."
    if state != "applied":
        reason = "Check the saved error and the current CRM record before resuming this approved update." if state == "approved" else ""
        return state, reason
    result = json.loads(row["result"] or "{}")
    account = accounts.get(result.get("account_id") or p["account_id"])
    if not account:
        return "approved", "Meridian did not return this account. Check its account ID before retrying."
    changes = dict(p["changes"])
    if p["kind"] in ("create", "chow"):
        changes.update({k:p["location"][k] for k in
                        ("name","billing_street","billing_city","billing_state","billing_zip","care_type")})
        changes.update(parent_id=p["parent_id"],status="Active")
    if p["kind"] == "chow":
        old = accounts.get(p["account_id"], {})
        if old.get("chow_current_account") != account["account_id"] or old.get("parent_id") != p["before"]["parent_id"]:
            return "approved", "Check the old billing account's parent and its link to the new account."
    mismatches = [k for k,v in changes.items() if account.get(k) != v]
    if mismatches:
        key = mismatches[0]
        return "approved", f"Meridian shows {account.get(key)} for {key}. The approved value was {changes[key]}. Compare both with the source before correcting it."
    if p["kind"] == "absent":
        if p["title"] == "Bellhaven of Sandusky":
            return "approved", "Missing from the website. Millstone shares this address. Verify the operator before changing the parent or moving billing."
        return "approved", "Missing from the website at review. Ask the facility who operates it before changing its parent."
    if p["kind"] == "investigate":
        return "approved", "CRM was flagged for review. Confirm who operates this facility."
    if p["title"] in UNCERTAIN and p["kind"] in ("update","duplicate"):
        if p["kind"] == "update":
            return "approved", "Three Kettering accounts shared an address. Confirm which account represents the active facility."
        old_name = p["before"]["name"]
        return "approved", f"{old_name} was marked inactive. Check with the operator whether it ran a separate service at the shared address."
    if p["kind"] == "duplicate":
        survivor = accounts.get(changes.get("duplicate_of_account"), {})
        if survivor.get("status") != "Active" or survivor.get("parent_id") != p["parent_id"]:
            return "approved", "Check the parent and status of the linked account."
    return "applied", ""


def current_panel(row, accounts, reason):
    proposal = json.loads(row["payload"])
    result = json.loads(row["result"] or "{}")
    ids = dict.fromkeys(x for x in (proposal["account_id"], result.get("account_id")) if x)
    parts = ["<section><h3>Current Meridian CRM data</h3>"]
    if reason:
        parts.append("<p class='warning'>" + esc(reason) + "</p>")
    for aid in ids:
        a = accounts.get(aid)
        if a:
            parts.append("<p><a href='" + crm_link(aid) + "'>" + esc(a["name"]) + "</a> · " +
                         esc(a["parent_name"] or "No parent") + " · " + esc(a["status"]) +
                         "<br>" + esc(a["billing_street"]) + ", " + esc(a["billing_city"]) +
                         " · Unpaid balance: $" + esc(a["outstanding_ar"]) + "</p>")
    if not ids:
        parts.append("<p>This proposal has no linked CRM account yet.</p>")
    return "".join(parts) + "</section>"
