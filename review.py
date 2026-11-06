"""Requirement 3: record approval or rejection before any CRM write."""

import json
import settings
import crm
import scraper
from storage import lock, db, audit
from common import now
from updates import apply_proposal


def decide(proposal_id, decision, reviewer, reason):
    """Record the reviewer decision before allowing any CRM write."""
    if (
        decision not in ("approve", "reject")
        or not reviewer.strip()
        or not reason.strip()
    ):
        raise ValueError("Reviewer, decision and rationale required")
    with lock():
        connection = db()
        row = connection.execute(
            "SELECT * FROM proposals WHERE id=?", (proposal_id,)
        ).fetchone()
        if not row:
            raise ValueError("Unknown proposal")
        if row["state"] in ("applied", "rejected"):
            return {"state": row["state"]}
        if row["state"] not in ("pending", "approved"):
            raise ValueError("Proposal no longer current")
        if row["state"] == "approved" and decision == "reject":
            raise ValueError(
                "Approved write may be partially applied; recover it first"
            )
        if row["state"] == "pending" and decision == "approve":
            proposal = json.loads(row["payload"])
            if proposal["kind"] == "absent":
                scraper.verify_absent(proposal["before"])
            if proposal["account_id"]:
                crm.validate_before(
                    proposal["before"], crm.account(proposal["account_id"])
                )
            if proposal["location"]:
                location = proposal["location"]
                path = location["source_url"].removeprefix(settings.BASE)
                fresh = scraper.parse_location(path, crm.request(path))
                for k in (
                    "name",
                    "billing_street",
                    "billing_city",
                    "billing_state",
                    "billing_zip",
                    "care_type",
                    "administrator",
                ):
                    if fresh[k] != location[k]:
                        raise RuntimeError(
                            "Website evidence changed: "
                            + k
                            + ". Rerun before approving."
                        )
        connection.execute(
            "UPDATE proposals SET state=?,reviewer=?,reason=?,decided_at=? WHERE id=?",
            (
                "approved" if decision == "approve" else "rejected",
                reviewer,
                reason,
                now(),
                proposal_id,
            ),
        )
        connection.commit()
        audit(
            connection, proposal_id, decision, {"reviewer": reviewer, "reason": reason}
        )
        if decision == "reject":
            return {"state": "rejected"}
        try:
            return apply_proposal(connection, json.loads(row["payload"]))
        except Exception as e:
            connection.execute(
                "UPDATE proposals SET error=? WHERE id=?", (str(e), proposal_id)
            )
            connection.commit()
            audit(connection, proposal_id, "error", str(e))
            raise
        finally:
            connection.close()
