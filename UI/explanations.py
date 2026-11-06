"""Plain-language summaries. Saved evidence and decisions are never changed."""

ACTION_LABELS = {
    "create": "New account",
    "update": "Update details",
    "duplicate": "Duplicate account",
    "chow": "Ownership change",
    "absent": "Not on website",
    "investigate": "Needs a closer look",
}

FIELD_LABELS = {
    "name": "Facility name",
    "billing_street": "Street address",
    "billing_city": "City",
    "billing_state": "State",
    "billing_zip": "ZIP code",
    "care_type": "Care services",
    "parent_id": "Parent company ID",
    "phone": "Phone",
    "status": "Account status",
    "note": "Saved note",
    "duplicate_of_account": "Account kept (ID)",
    "chow_current_account": "New account (ID)",
}


def explanation(proposal, state, confirmation=None):
    """Describe completed actions in the past; keep proposals conditional."""
    kind = proposal["kind"]
    done = state == "applied"
    before = proposal.get("before") or {}
    location = proposal.get("location") or {}
    changes = proposal.get("changes") or {}
    if state == "rejected":
        if "billing_street" in changes and before.get(
            "billing_street", ""
        ).lower().startswith("po box"):
            return "Kept the billing PO box. The website's street address does not mean the billing address is wrong."
        return "Rejected this change. The account was not changed by this proposal. See the review note below."
    if kind == "create":
        city = location.get("billing_city", "this location")
        text = f"No matching account for this facility in {city} was found during the review. "
        text += (
            "Created a new Bellhaven account."
            if done
            else "Proposed: create a new Bellhaven account."
        )
        other_cities = sorted(
            {
                r.get("billing_city")
                for r in proposal.get("related", [])
                if r.get("billing_city") and r.get("billing_city") != city
            }
        )
        if other_cities:
            text += (
                " Similar names in "
                + ", ".join(other_cities)
                + " have different addresses."
            )
        return text
    if kind == "chow":
        return (
            "The old account has billing history and unpaid bills. "
            + ("Created" if done else "Proposed: create")
            + " a new Bellhaven account and "
            + ("linked" if done else "link")
            + " it from the old account, keeping the old billing details unchanged."
        )
    if kind == "absent":
        return (
            "Not listed on Bellhaven's website when checked. "
            + ("Flagged" if done else "Proposed: flag")
            + " for review and "
            + ("kept" if done else "keep")
            + " the parent unchanged. A sale or closure is not confirmed."
        )
    if kind == "duplicate":
        text = (
            "Accounts matched this address. Marked this one as a duplicate, made it inactive, and linked it to the account kept."
            if done
            else "Possible duplicate. Proposed: make this account inactive and link it to the account to keep."
        )
        text += (
            " A shared address alone does not prove two accounts are the same facility."
        )
        return text
    if kind == "update":
        parts = []
        if "name" in changes:
            parts.append(
                ("Changed" if done else "Change") + " the name to match the website."
            )
        if "parent_id" in changes:
            parts.append(
                ("Linked" if done else "Link")
                + " this facility to Bellhaven, as listed on its website."
            )
        fields = [
            FIELD_LABELS.get(key, key.replace("_", " ")).lower()
            for key in changes
            if key not in ("name", "parent_id", "note")
        ]
        if fields:
            parts.append(
                ("Updated" if done else "Update")
                + " the "
                + ", ".join(fields)
                + " to match the website."
            )
        text = " ".join(parts) or "Review the proposed details below."
        if not done:
            text = "Proposed: " + text[0].lower() + text[1:]
        if confirmation and "unconfirmed" in confirmation["reason"].lower():
            text += " Which account to keep still needs confirmation."
        return text
    return "These records need a closer look. Check the website and account details before deciding."
