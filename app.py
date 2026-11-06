"""Serve the local review app. Reads render pages; POST records decisions."""

import json
import os
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import settings
import storage
import review
import crm
from ui.live_status import classify, current_panel
import reconcile
from ui.layout import layout, esc
from ui.pages import queue_page, locations_page
from ui.proposal import proposal_page

CSRF = secrets.token_urlsafe(32)
REPLAY_INSTANCE = None


class Handler(BaseHTTPRequestHandler):
    def send(self, body, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(layout(body).encode())

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        if url.path.startswith("/crm/"):
            account_id = url.path.split("/")[-1]
            if not account_id.isalnum():
                return self.send("Invalid account", 400)
            self.send_response(303)
            self.send_header(
                "Location",
                settings.BASE
                + "/crm/"
                + os.environ["CRM_TOKEN"]
                + "/accounts/"
                + account_id,
            )
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            return
        if url.path == "/matches":
            path = settings.DATA / "matches.json"
            matches = json.loads(path.read_text()) if path.exists() else []
            return self.send(locations_page(matches))
        connection = storage.db()
        try:
            if url.path == "/api/proposals":
                rows = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM proposals ORDER BY created_at,id"
                    )
                ]
                for row in rows:
                    row["payload"] = json.loads(row["payload"])
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "csrf": CSRF,
                            "proposals": rows,
                            "replay_instance": REPLAY_INSTANCE,
                        }
                    ).encode()
                )
                return
            try:
                accounts = {a["account_id"]: a for a in crm.all_records("accounts")}
            except Exception:
                return self.send("<p>Could not read Meridian CRM. Refresh to try again.</p>", 503)
            proposal_id = query.get("id", [""])[0]
            if proposal_id:
                row = connection.execute(
                    "SELECT * FROM proposals WHERE id=?", (proposal_id,)
                ).fetchone()
                if not row:
                    return self.send("Not found", 404)
                confirmation = connection.execute(
                    "SELECT * FROM confirmations WHERE proposal_id=?", (proposal_id,)
                ).fetchone()
                category, reason = classify(row, accounts)
                return self.send(proposal_page(row, CSRF, confirmation, category, current_panel(row, accounts, reason)))
            rows = connection.execute(
                "SELECT * FROM proposals ORDER BY created_at,id"
            ).fetchall()
            return self.send(queue_page(rows, query.get("state", ["all"])[0], {r["id"]: classify(r, accounts) for r in rows}))
        finally:
            connection.close()

    def do_POST(self):
        if self.path not in ("/decide", "/api/decisions"):
            return self.send("Not found", 404)
        if self.headers.get("Host") not in (
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        ):
            return self.send("Invalid host", 403)
        n = int(self.headers.get("Content-Length", "0"))
        if n > 20000:
            return self.send("Request too large", 413)
        raw = self.rfile.read(n).decode()
        form = (
            json.loads(raw)
            if self.path == "/api/decisions"
            else {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
        )
        if not secrets.compare_digest(form.get("csrf", ""), CSRF):
            return self.send("Invalid CSRF token", 403)
        try:
            review.decide(
                form.get("id", ""),
                form.get("decision", ""),
                form.get("reviewer", ""),
                form.get("reason", ""),
            )
        except Exception as e:
            return self.send(
                "<h2>Write stopped safely</h2><p>"
                + esc(e)
                + '</p><a href="/?id='
                + esc(form.get("id", ""))
                + '">Return to review / recovery</a>',
                409,
            )
        if self.path == "/api/decisions":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"id": form["id"], "decision": form["decision"], "verified": True}
                ).encode()
            )
            return
        self.send_response(303)
        self.send_header("Location", "/?id=" + form["id"])
        self.end_headers()


def main():
    print("Fetching the live website and CRM accounts...", flush=True)
    reconcile.pipeline()
    print("Review app: http://127.0.0.1:8765", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()


if __name__ == "__main__":
    main()
