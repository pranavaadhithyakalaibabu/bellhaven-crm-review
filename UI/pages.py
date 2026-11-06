"""Queue summary and website coverage pages."""

import json
from ui.layout import NAV, esc, STATUS_LABELS, STATUS_HELP
from ui.explanations import ACTION_LABELS


def queue_page(rows, state, categories):
    counts = {
        s: sum(categories[x["id"]][0] == s for x in rows)
        for s in ["pending", "applied", "rejected", "approved"]
    }
    body = (
        NAV
        + '<div class="metrics">'
        + "".join(
            '<div class="metric"><strong class="num">'
            + str(v)
            + "</strong>"
            + esc(STATUS_LABELS[s])
            + "<p><small>"
            + esc(STATUS_HELP[s])
            + "</small></p></div>"
            for s, v in counts.items()
        )
        + "</div>"
    )
    body += (
        "<section><h2>"
        + esc(STATUS_LABELS.get(state, state))
        + "</h2><table><tr><th>Facility</th><th>Action</th><th>Status</th><th>Review</th></tr>"
    )
    for row in rows:
        bucket, reason = categories[row["id"]]
        if state != "all" and bucket != state:
            continue
        proposal = json.loads(row["payload"])
        body += (
            "<tr><td>"
            + esc(proposal["title"])
            + "</td><td>"
            + esc(ACTION_LABELS.get(proposal["kind"], proposal["kind"]))
            + "</td><td>"
            + esc(STATUS_LABELS.get(bucket, bucket)) + ("<br><small>" + esc(reason) + "</small>" if reason else "")
            + '</td><td><a href="/?id='
            + proposal["id"]
            + '">'
            + (
                "Review "
                if row["state"] in ("pending", "approved")
                else "View decision: "
            )
            + esc(proposal["title"])
            + " · "
            + esc(ACTION_LABELS.get(proposal["kind"], proposal["kind"]))
            + "</a></td></tr>"
        )
    return body + "</table></section>"


def locations_page(matches):
    return (
        NAV
        + "<h2>Location coverage</h2><pre>"
        + esc(json.dumps(matches, indent=2))
        + "</pre>"
    )
