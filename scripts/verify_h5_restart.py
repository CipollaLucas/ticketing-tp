"""Verify durable H5 purchases after app-container restarts, without restarting databases.

Only runs against an explicitly marked disposable CI Gateway and fixture evidence.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID


def request(method: str, path: str, *, token: str = "", key: str = "", payload=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if key:
        headers["Idempotency-Key"] = key
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        "http://127.0.0.1:8091" + path, method=method, data=data, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, response.headers, json.load(response)
    except urllib.error.HTTPError as error:
        raise AssertionError(
            f"{method} {path}: unexpected HTTP {error.code}"
        ) from error


def main() -> None:
    if os.environ.get("H5_DISPOSABLE_RESTART_UAT") != "yes":
        raise SystemExit("REFUSED: restart evidence needs disposable H5 UAT")
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_h5_restart.py <disposable smoke log>")
    log = Path(sys.argv[1]).read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for field in ("EVENT_ID", "ORDER_ID", "TICKET_ID", "ZONE_ID", "KEY"):
        matches = re.findall(
            r"^H5_RESTART_" + field + r"=([^\r\n]+)$", log, re.MULTILINE
        )
        if len(matches) != 1:
            raise SystemExit(f"Missing or duplicated disposable evidence: {field}")
        values[field] = matches[0]
    for field in ("EVENT_ID", "ORDER_ID", "TICKET_ID", "ZONE_ID"):
        UUID(values[field])
    if not values["KEY"].startswith("h5-"):
        raise SystemExit("REFUSED: unexpected idempotency key")
    password = os.environ["H3_TEST_PASSWORD"]
    status, _, auth = request(
        "POST", "/api/v1/auth/login",
        payload={"username": "h3customer", "password": password},
    )
    assert status == 200
    token = auth["access_token"]

    status, _, inventory = request(
        "GET", f"/api/v1/events/{values['EVENT_ID']}/inventory"
    )
    assert status == 200
    zone = next(z for z in inventory["zones"] if z["id"] == values["ZONE_ID"])
    assert zone["available"] == 1, "Ticket stock changed during service restarts"
    status, _, tickets = request("GET", "/api/v1/me/tickets", token=token)
    assert status == 200
    assert any(t["id"] == values["TICKET_ID"] for t in tickets["items"])

    status, headers, replay = request(
        "POST", "/api/v1/orders", token=token, key=values["KEY"],
        payload={
            "event_id": values["EVENT_ID"],
            "items": [
                {"zone_id": values["ZONE_ID"], "quantity": 1, "seat_ids": []}
            ],
        },
    )
    assert status == 200, "Same-key purchase after restart must be a replay"
    assert headers.get("Idempotent-Replayed") == "true"
    assert replay["id"] == values["ORDER_ID"]
    assert any(t["id"] == values["TICKET_ID"] for t in replay["tickets"])
    _, _, stock_after = request(
        "GET", f"/api/v1/events/{values['EVENT_ID']}/inventory"
    )
    assert next(
        z for z in stock_after["zones"] if z["id"] == values["ZONE_ID"]
    )["available"] == 1
    print("PASS: Identity login and Events inventory after app restarts")
    print("PASS: Ticketing order and ticket survived app restarts")
    print("PASS: identical key replayed one order; stock not decremented twice")


if __name__ == "__main__":
    main()
