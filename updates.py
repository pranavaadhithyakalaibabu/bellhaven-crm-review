"""Apply an approved change, enforce CHOW and verify the CRM result."""

import crm
import scraper
from common import encode
from storage import audit
from normalization import norm, street
from billing import financial_protected


def apply_proposal(connection, proposal):
    """Apply an approved proposal and check the CRM response by reading it back."""
    proposal_id = proposal["id"]
    row = connection.execute(
        "SELECT * FROM proposals WHERE id=?", (proposal_id,)
    ).fetchone()
    if row["state"] != "approved":
        raise RuntimeError("No approval recorded")
    current = crm.account(proposal["account_id"]) if proposal["account_id"] else None
    marker = "[Bellhaven reconciliation " + proposal_id + "]"
    if proposal["kind"] in ("create", "chow"):
        existing = [
            account_record
            for account_record in crm.all_records("accounts")
            if marker in account_record.get("note", "")
        ]
        if len(existing) > 1:
            raise RuntimeError("Multiple creation markers; investigate")
        if existing:
            new = existing[0]
        else:
            if row["phase"] == "post_sent":
                raise RuntimeError(
                    "Create outcome unknown; no automatic retry. Investigate server before resetting journal."
                )
            if current:
                crm.validate_before(proposal["before"], current)
                if not financial_protected(current):
                    raise RuntimeError("Billing condition changed; regenerate proposal")
            location = proposal["location"]
            payload = {
                k: location[k]
                for k in [
                    "name",
                    "billing_street",
                    "billing_city",
                    "billing_state",
                    "billing_zip",
                    "care_type",
                    "phone",
                ]
            } | {"parent_id": proposal["parent_id"], "status": "Active"}
            # Re-check identity immediately before POST, including another reviewer's creations.
            collision = [
                account_record
                for account_record in crm.all_records("accounts")
                if account_record["parent_id"] == proposal["parent_id"]
                and not account_record["duplicate_of_account"]
                and not account_record["chow_current_account"]
                and street(account_record["billing_street"])
                == street(location["billing_street"])
                and norm(account_record["billing_city"])
                == norm(location["billing_city"])
                and account_record["billing_state"] == location["billing_state"]
            ]
            if collision:
                raise RuntimeError(
                    "A matching current account already exists; rerun and review instead of creating"
                )
            payload["note"] = (
                marker
                + " Source: "
                + location["source_url"]
                + (
                    " CHOW from "
                    + current["account_id"]
                    + "; old billing account retained."
                    if current
                    else ""
                )
            )
            connection.execute(
                "UPDATE proposals SET phase='post_sent' WHERE id=?", (proposal_id,)
            )
            connection.commit()
            audit(connection, proposal_id, "create_intent", payload)
            new = crm.request("/api/v1/accounts", "POST", payload)
            new = new.get("data", new)
        account_id = new["account_id"]
        connection.execute(
            "UPDATE proposals SET phase='created',result=? WHERE id=?",
            (encode(new), proposal_id),
        )
        connection.commit()
        if current:
            if current.get("chow_current_account") != account_id:
                crm.validate_before(proposal["before"], current)
                crm.request(
                    "/api/v1/accounts/" + current["account_id"],
                    "PATCH",
                    {"chow_current_account": account_id},
                )
            old = crm.account(current["account_id"])
            for k, v in proposal["before"].items():
                if k not in ("updated_at", "chow_current_account") and old.get(k) != v:
                    raise RuntimeError("CHOW old-account preservation failed: " + k)
            if old["chow_current_account"] != account_id:
                raise RuntimeError("CHOW link verification failed")
        result = crm.account(account_id)
        for k in [
            "name",
            "billing_street",
            "billing_city",
            "billing_state",
            "billing_zip",
            "care_type",
        ]:
            if result[k] != proposal["location"][k]:
                raise RuntimeError("Create readback mismatch: " + k)
        if result["parent_id"] != proposal["parent_id"]:
            raise RuntimeError("Create parent mismatch")
    else:
        changes = proposal["changes"]
        already = all(current.get(k) == v for k, v in changes.items())
        if not already:
            crm.validate_before(proposal["before"], current)
            if proposal["kind"] == "absent":
                scraper.verify_absent(current)
                current = crm.account(proposal["account_id"])
                crm.validate_before(proposal["before"], current)
            if (
                "parent_id" in changes
                and changes["parent_id"] != current["parent_id"]
                and financial_protected(current)
            ):
                raise RuntimeError("Protected billing history: re-parent blocked")
            if proposal["kind"] == "duplicate":
                survivor = crm.account(changes["duplicate_of_account"])
                if (
                    survivor["status"] != "Active"
                    or survivor["parent_id"] != proposal["parent_id"]
                    or survivor["duplicate_of_account"]
                ):
                    raise RuntimeError(
                        "Approve survivor correction before retiring duplicate"
                    )
            audit(connection, proposal_id, "patch_intent", changes)
            crm.request("/api/v1/accounts/" + proposal["account_id"], "PATCH", changes)
        result = crm.account(proposal["account_id"])
        if any(result.get(k) != v for k, v in changes.items()):
            raise RuntimeError("Patch readback mismatch")
    connection.execute(
        "UPDATE proposals SET state='applied',result=?,error=NULL WHERE id=?",
        (encode(result), proposal_id),
    )
    connection.commit()
    audit(connection, proposal_id, "verified", result)
    return result
