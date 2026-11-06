"""Requirement 4: run a fresh comparison. Safe to schedule; never approves changes."""

import settings
import scraper
import crm
import matching
from storage import lock, db
from common import now, save, encode


def pipeline():
    """Save source evidence and queue new proposals. Never approve changes here."""
    with lock():
        locations, pages = scraper.scrape()
        accounts = crm.all_records("accounts")
        contacts = crm.all_records("contacts")
        proposals, matches, parent = matching.propose(locations, accounts, contacts)
        run = now().replace(":", "-")
        snapshot_dir = settings.DATA / "snapshots" / run
        snapshot_dir.mkdir(parents=True)
        for filename, contents in [
            ("pages", pages),
            ("locations", locations),
            ("accounts", accounts),
            ("contacts", contacts),
            ("matches", matches),
        ]:
            save(snapshot_dir / (filename + ".json"), contents)
        save(settings.DATA / "locations.json", locations)
        save(settings.DATA / "matches.json", matches)
        connection = db()
        inserted = 0
        ids = [proposal["id"] for proposal in proposals]
        for proposal in proposals:
            inserted += connection.execute(
                "INSERT OR IGNORE INTO proposals(id,payload,created_at) VALUES(?,?,?)",
                (proposal["id"], encode(proposal), now()),
            ).rowcount
            connection.execute(
                "UPDATE proposals SET payload=? WHERE id=? AND state='pending'",
                (encode(proposal), proposal["id"]),
            )
        for row in connection.execute(
            "SELECT id FROM proposals WHERE state='pending'"
        ).fetchall():
            if row["id"] not in ids:
                connection.execute(
                    "UPDATE proposals SET state='superseded' WHERE id=?", (row["id"],)
                )
        summary = dict(
            run=run,
            locations=len(locations),
            accounts=len(accounts),
            new_proposals=inserted,
            parent_id=parent,
            snapshot=str(snapshot_dir.relative_to(settings.DATA)),
        )
        connection.execute("INSERT INTO runs VALUES(?,?)", (run, encode(summary)))
        connection.commit()
        connection.close()
        print(encode(summary))
        return summary


if __name__ == "__main__":
    pipeline()
