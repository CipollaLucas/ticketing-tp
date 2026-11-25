"""Disposable reverse proxy: hide ONE successful Ticketing write acknowledgement.

Not a production service. It forwards only the private sale-gate endpoint to
a fixed upstream; a matching X-Request-ID on POST makes it commit upstream,
then return an artificial 503 to Events instead of the successful response.
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import urlsplit

import httpx

UPSTREAM = os.environ["H4_FAULT_UPSTREAM"].rstrip("/")
assert UPSTREAM == "http://h4-ticketing:8003"
assert os.environ.get("H4_DISPOSABLE_UAT") == "yes"
LOST = {
    "h4-lost-publish-ack": "/commands",
    "h4-lost-unpublish-ack": "/close-without-sales",
}
seen: set[str] = set()
guard = Lock()


class Proxy(BaseHTTPRequestHandler):
    def do_GET(self):
        self.forward()

    def do_PUT(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        parsed = urlsplit(self.path)
        if (
            parsed.query or parsed.fragment
            or not parsed.path.startswith("/api/v1/internal/sales/gates/")
            or ".." in parsed.path
            or self.command not in {"GET", "PUT", "POST"}
        ):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 8192:
            self.send_error(413)
            return
        payload = self.rfile.read(length) if length else b""
        headers = {}
        for key in ("X-Internal-Service-Token", "X-Request-ID", "Content-Type"):
            if key in self.headers:
                headers[key] = self.headers[key]
        try:
            with httpx.Client(timeout=8, trust_env=False, follow_redirects=False) as cli:
                upstream = cli.request(
                    self.command, UPSTREAM + parsed.path,
                    headers=headers, content=payload,
                )
        except httpx.RequestError:
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        marker = self.headers.get("X-Request-ID", "")
        hide = False
        if (
            self.command == "POST" and upstream.status_code == 200
            and marker in LOST and parsed.path.endswith(LOST[marker])
        ):
            with guard:
                if marker not in seen:
                    seen.add(marker)
                    hide = True
        if hide:
            # Upstream has ALREADY committed; Events cannot infer success.
            response = b'{"detail":"injected lost upstream acknowledgement"}'
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            print(f"FAULT INJECTED after Ticketing commit: {marker}", flush=True)
            return

        self.send_response(upstream.status_code)
        body = upstream.content
        if "content-type" in upstream.headers:
            self.send_header("Content-Type", upstream.headers["content-type"])
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Never log bearer tokens or internal credentials.
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8004), Proxy).serve_forever()
