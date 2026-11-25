"""CI-only dry run of pre-write abort and post-write guard using a real H5 ticket.

No Legacy endpoint is contacted or changed; the Legacy ledger is synthetic.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from uuid import UUID

from h5_abort_guard import Decision, Reconciliation, decide_abort

GATEWAY = "http://127.0.0.1:8091"


def fixture(log: str, field: str) -> str:
    matches = re.findall(
        rf"^H5_RESTART_{field}=([^\r\n]+)$", log, re.MULTILINE
    )
    if len(matches) != 1:
        raise ValueError(f"Expected one disposable fixture {field}")
    return str(UUID(matches[0]))


def request(path: str, token: str = "") -> dict:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(
        urllib.request.Request(GATEWAY + path, headers=headers), timeout=15
    ) as response:
        if response.status != 200:
            raise AssertionError(f"Unexpected Gateway status {response.status}")
        return json.load(response)


def main() -> None:
    if (
        os.environ.get("H5_DISPOSABLE_ABORT_UAT") != "yes"
        or os.environ.get("H5_PROJECT") != "h5-gateway-ci"
        or len(sys.argv) != 2
    ):
        raise SystemExit("REFUSED: only disposable H5 project may run abort dry-run")
    log = Path(sys.argv[1]).read_text(encoding="utf-8")
    ticket_id = fixture(log, "TICKET_ID")
    event_id = fixture(log, "EVENT_ID")
    prewrite = Reconciliation(
        new_confirmed_ticket_ids=frozenset(),
        legacy_known_ticket_ids=frozenset(),
        new_writes_frozen=True,
        verified_single_writer=True,
    )
    assert decide_abort(prewrite) is Decision.SAFE_PREWRITE_ABORT

    password = os.environ["H3_TEST_PASSWORD"]
    payload = json.dumps({"username": "h3customer", "password": password}).encode()
    with urllib.request.urlopen(
        urllib.request.Request(
            GATEWAY + "/api/v1/auth/login",
            data=payload,
            headers={"Content-Type": "application/json"},
        ),
        timeout=15,
    ) as response:
        assert response.status == 200
        token = json.load(response)["access_token"]
    tickets = request("/api/v1/me/tickets?limit=100", token)["items"]
    if not any(t["id"] == ticket_id for t in tickets):
        raise AssertionError("Confirmed H5 fixture ticket not visible to customer")
    event = request(f"/api/v1/events/{event_id}")
    if event["status"] != "published":
        raise AssertionError("Fixture event not published")

    # Simulated legacy ledger is intentionally empty: it does not own this ticket.
    postwrite = Reconciliation(
        new_confirmed_ticket_ids=frozenset({ticket_id}),
        legacy_known_ticket_ids=frozenset(),
        new_writes_frozen=False,
        verified_single_writer=False,
    )
    assert decide_abort(postwrite) is Decision.BLOCK_UNRECONCILED_POSTWRITE_ABORT
    frozen = Reconciliation(
        new_confirmed_ticket_ids=postwrite.new_confirmed_ticket_ids,
        legacy_known_ticket_ids=postwrite.legacy_known_ticket_ids,
        new_writes_frozen=True,
        verified_single_writer=True,
    )
    assert decide_abort(frozen) is Decision.BLOCK_UNRECONCILED_POSTWRITE_ABORT
    # Even hypothetical matching synthetic records do not authorize a switch.
    matched = Reconciliation(
        new_confirmed_ticket_ids=frozenset({ticket_id}),
        legacy_known_ticket_ids=frozenset({ticket_id}),
        new_writes_frozen=True,
        verified_single_writer=True,
    )
    assert decide_abort(matched) is Decision.RECONCILIATION_REVIEW_REQUIRED
    print("PASS: pre-write synthetic abort is safe")
    print("PASS: real H5 confirmed ticket blocks unreconciled Legacy rollback")
    print("PASS: even simulated matching records still require independent review")
    print("NO ROUTING CHANGES OR LEGACY WRITES PERFORMED")


if __name__ == "__main__":
    main()
