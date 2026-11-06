"""Requirement 2: match locations and propose corrections without writing."""

import difflib
from common import digest
from normalization import norm, street
from billing import financial_protected


def propose(locations, accounts, contacts):
    """Compare website locations with CRM accounts without writing to the CRM."""
    parents = [
        account_record
        for account_record in accounts
        if account_record["name"] == "Bellhaven Senior Living (Parent Account)"
        and not account_record["parent_id"]
    ]
    if len(parents) != 1:
        raise RuntimeError("Cannot identify unique Bellhaven parent")
    parent_id = parents[0]["account_id"]
    proposals = []
    matches = []
    matched_account_ids = set()
    live = [
        account_record
        for account_record in accounts
        if account_record["account_id"] != parent_id
        and not account_record.get("duplicate_of_account")
        and not account_record.get("chow_current_account")
        and "(Parent Account)" not in account_record["name"]
    ]

    def add(kind, account_record, changes, location, reason, related=None):
        proposal = dict(
            kind=kind,
            account_id=account_record["account_id"] if account_record else None,
            title=location["name"] if location else account_record["name"],
            before=account_record,
            changes=changes,
            location=location,
            reason=reason,
            related=related or [],
            parent_id=parent_id,
        )
        # Decision identity excludes volatile fetch/update timestamps. Rejected content stays rejected.
        proposal["id"] = digest(
            {
                "kind": kind,
                "target": proposal["account_id"] or location["source_url"],
                "changes": changes,
            }
        )[:24]
        proposals.append(proposal)

    # Address is the strongest match; name alone must also agree on city/state.
    for location in locations:
        same_city = [
            account_record
            for account_record in live
            if norm(account_record["billing_city"]) == norm(location["billing_city"])
            and account_record["billing_state"] == location["billing_state"]
        ]
        exact = [
            account_record
            for account_record in same_city
            if street(account_record["billing_street"])
            == street(location["billing_street"])
        ]
        name_matches = [
            account_record
            for account_record in same_city
            if norm(account_record["name"]) == norm(location["name"])
        ]
        candidates = exact or name_matches
        if not candidates:
            similar_accounts = [
                account_record
                for account_record in live
                if norm(account_record["name"]) == norm(location["name"])
                or (
                    account_record in same_city
                    and difflib.SequenceMatcher(
                        None, norm(account_record["name"]), norm(location["name"])
                    ).ratio()
                    > 0.55
                )
            ]
            add(
                "create",
                None,
                {
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
                }
                | {"parent_id": parent_id, "status": "Active"},
                location,
                "No full-address or exact-name + city/state match in all CRM accounts. Similar names at other addresses are not identity evidence.",
                similar_accounts,
            )
            matches.append(
                dict(
                    location=location["name"],
                    classification="missing",
                    candidates=[
                        account_record["account_id"]
                        for account_record in similar_accounts
                    ],
                )
            )
            continue

        def rank(account_record):
            administrator_matches = any(
                contact["account_id"] == account_record["account_id"]
                and contact.get("is_active")
                and norm(contact["name"]) == norm(location["administrator"])
                for contact in contacts
            )
            return (
                administrator_matches,
                float(account_record["lifetime_revenue"]) > 0,
                account_record["parent_id"] == parent_id,
                norm(account_record["name"]) == norm(location["name"]),
                account_record["parent_name"].startswith("Harborview"),
                len(
                    [
                        contact
                        for contact in contacts
                        if contact["account_id"] == account_record["account_id"]
                    ]
                ),
                account_record["account_id"],
            )

        candidates.sort(key=rank, reverse=True)
        account_record = candidates[0]
        matched_account_ids.update(x["account_id"] for x in candidates)
        if account_record["account_id"] in [
            match.get("account_id") for match in matches
        ]:
            raise RuntimeError(
                "One account matches multiple locations; manual investigation required"
            )
        changes = {}
        for field in [
            "name",
            "billing_street",
            "billing_city",
            "billing_state",
            "billing_zip",
            "care_type",
        ]:
            same = (
                street(account_record[field]) == street(location[field])
                if field == "billing_street"
                else account_record[field] == location[field]
            )
            if not same:
                changes[field] = location[field]
        if account_record["parent_id"] != parent_id:
            changes["parent_id"] = parent_id
        if account_record["status"] != "Active":
            changes["status"] = "Active"
        evidence = (
            (
                "Normalized street + city/state match"
                if exact
                else "Exact name + city/state; street differs and requires review"
            )
            + ". Website administrator: "
            + location["administrator"]
            + ". Survivor preference: matching administrator, revenue history, current parent/name, acquisition context, contacts, stable ID."
        )
        administrator_supported = any(
            contact["account_id"] == account_record["account_id"]
            and contact.get("is_active")
            and norm(contact["name"]) == norm(location["administrator"])
            for contact in contacts
        )
        if len(candidates) > 1 and not administrator_supported:
            evidence += " Several accounts share this address. The survivor is a review choice; separate identities are not independently confirmed."
        kind = (
            "chow"
            if "parent_id" in changes and financial_protected(account_record)
            else "update"
        )
        if changes:
            add(kind, account_record, changes, location, evidence, candidates[1:])
        matches.append(
            dict(
                location=location["name"],
                account_id=account_record["account_id"],
                classification=kind if changes else "confident_match",
                evidence=evidence,
            )
        )
        # Keep one current account and explain what happens to each extra copy.
        for loser in candidates[1:]:
            if (
                float(loser["lifetime_revenue"]) > 0
                or float(loser["outstanding_ar"]) > 0
                or loser["care_type"] != account_record["care_type"]
            ):
                review_note = (
                    "Co-located account; financial history or differing care type "
                    "prevents safe duplicate classification. " + location["source_url"]
                )
                if (
                    loser["status"] == "Needs Review"
                    and review_note in loser["note"].splitlines()
                ):
                    continue
                note = loser["note"]
                if review_note not in note.splitlines():
                    note = (note + "\n" + review_note).strip()
                add(
                    "investigate",
                    loser,
                    {
                        "status": "Needs Review",
                        "note": note,
                    },
                    location,
                    "Shared address alone is insufficient to retire a financially active or distinct-care account.",
                    [account_record],
                )
                continue
            add(
                "duplicate",
                loser,
                {
                    "status": "Inactive",
                    "duplicate_of_account": account_record["account_id"],
                    "note": (
                        loser["note"]
                        + "\nDuplicate of "
                        + account_record["account_id"]
                        + ". Same normalized address, city/state and care type. "
                        + (
                            "Survivor has the website administrator contact. "
                            if administrator_supported
                            else "Survivor is a review choice; separate identities are not independently confirmed. "
                        )
                        + location["source_url"]
                    ).strip(),
                },
                location,
                evidence,
                [account_record],
            )
    # Website absence is a reason to investigate, not proof of a sale.
    for account_record in live:
        if (
            account_record["parent_id"] == parent_id
            and account_record["account_id"] not in matched_account_ids
            and account_record["status"] == "Active"
        ):
            related = [
                other_account
                for other_account in live
                if other_account["account_id"] != account_record["account_id"]
                and street(account_record["billing_street"])
                == street(other_account["billing_street"])
                and account_record["billing_city"] == other_account["billing_city"]
                and account_record["billing_state"] == other_account["billing_state"]
            ]
            note = "Not found in complete Bellhaven website crawl. Ownership/closure unconfirmed; verify before outreach or re-parenting."
            if related:
                note += (
                    " Co-located CRM records: "
                    + ", ".join(x["account_id"] + " " + x["name"] for x in related)
                    + ". CRM coexistence is not proof of a sale."
                )
            add(
                "absent",
                account_record,
                {
                    "status": "Needs Review",
                    "note": (account_record["note"] + "\n" + note).strip(),
                },
                None,
                note,
                related,
            )
    return proposals, matches, parent_id
