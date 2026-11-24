"""Real HTTP integration of independent Identity and Events services.

No Identity database access from Events. Tokens and passwords are never printed.
Run --phase online after startup, then --phase outage after stopping Identity.
"""
import argparse
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from events_service.persistence import EventRow, engine


def count_drafts() -> int:
    with Session(engine) as db:
        return db.scalar(select(func.count()).select_from(EventRow)) or 0


def payload() -> dict[str, str]:
    start = datetime.now(UTC) + timedelta(days=7)
    return {
        "name": "H3 isolated contract event",
        "description": "Safe independent draft",
        "venue": "H3 Test Venue",
        "start_at": start.isoformat(),
        "end_at": (start + timedelta(hours=2)).isoformat(),
    }


def login(http: httpx.Client, username: str, password: str) -> str:
    response = http.post("/api/v1/auth/login", json={
        "username": username, "password": password,
    })
    assert response.status_code == 200, f"Identity login failed: {response.status_code}"
    return response.json()["access_token"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["online", "outage"], required=True)
    phase = parser.parse_args().phase
    assert count_drafts() == (0 if phase == "online" else 1)
    events_url = os.environ["H3_EVENTS_URL"]
    with httpx.Client(base_url=events_url, timeout=5, trust_env=False) as events:
        assert events.get("/health").status_code == 200
        if phase == "outage":
            # No token is trusted or accepted if the remote authority is down.
            rejected = events.post(
                "/api/v1/events",
                json=payload(),
                headers={"Authorization": "Bearer plausible-but-invalid-token"},
            )
            assert rejected.status_code == 503, rejected.status_code
            assert count_drafts() == 1
            print("PASS: Identity outage -> Events 503, no additional writes")
            return

        with httpx.Client(
            base_url=os.environ["H3_IDENTITY_URL"], timeout=5, trust_env=False,
        ) as identity:
            password = os.environ["H3_TEST_PASSWORD"]
            owner = login(identity, "h3owner", password)
            customer = login(identity, "h3customer", password)
            owner_info = identity.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {owner}"},
            )
            assert owner_info.status_code == 200
            owner_id = UUID(owner_info.json()["id"])

            anonymous = events.post("/api/v1/events", json=payload())
            assert anonymous.status_code == 401
            denied = events.post(
                "/api/v1/events",
                json=payload(),
                headers={"Authorization": f"Bearer {customer}"},
            )
            assert denied.status_code == 403
            forged = events.post(
                "/api/v1/events",
                json=payload() | {"owner_id": str(UUID(int=1))},
                headers={"Authorization": f"Bearer {owner}"},
            )
            assert forged.status_code == 422
            assert count_drafts() == 0

            created = events.post(
                "/api/v1/events",
                json=payload(),
                headers={"Authorization": f"Bearer {owner}", "X-Request-ID": "h3-live-test"},
            )
            assert created.status_code == 201, created.status_code
            assert created.headers["cache-control"] == "no-store"
            assert UUID(created.json()["owner_id"]) == owner_id
            assert created.json()["status"] == "draft"
            assert count_drafts() == 1

            logout = identity.post(
                "/api/v1/auth/logout", headers={"Authorization": f"Bearer {owner}"},
            )
            assert logout.status_code == 204
            revoked = events.post(
                "/api/v1/events", json=payload(),
                headers={"Authorization": f"Bearer {owner}"},
            )
            assert revoked.status_code == 401
            assert count_drafts() == 1
    print("PASS: owner 201, customer 403, anonymous/revoked 401, forged owner 422")
    print("PASS: exactly one Events-owned draft committed via real Identity HTTP")


if __name__ == "__main__":
    main()
