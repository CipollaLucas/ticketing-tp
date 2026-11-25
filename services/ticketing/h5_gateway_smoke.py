"""Disposable real-HTTP H5 Stage I acceptance through Gateway only.

This never calls an internal service URL and refuses non-disposable databases.
No payment processing, productive routing or Legacy dependencies are involved.
"""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx

from ticketing_service.persistence import engine


def checked(reply: httpx.Response, status: int, label: str) -> dict:
    assert reply.status_code == status, (
        f"{label}: expected {status}, got {reply.status_code}: {reply.text[:180]}"
    )
    return reply.json()


def main() -> None:
    if engine.url.database != "h4_ticketing_test" or os.getenv("H5_DISPOSABLE_UAT") != "yes":
        raise SystemExit("REFUSED: H5 Gateway smoke requires disposable Ticketing DB")
    base = os.environ["H5_GATEWAY_URL"]
    assert base == "http://h5-gateway:8080", "REFUSED: H5 Gateway URL must be isolated"
    password = os.environ["H3_TEST_PASSWORD"]
    with httpx.Client(base_url=base, timeout=12, trust_env=False) as gateway:
        checked(gateway.get("/health"), 200, "Gateway health")
        assert gateway.get("/api/v1/internal/sales/availability").status_code == 404
        assert gateway.get("/api/v1/internal/auth/introspect").status_code == 404
        assert gateway.get("/api/v1/route-not-extracted").status_code == 503

        owner = checked(
            gateway.post(
                "/api/v1/auth/login",
                json={"username": "h3owner", "password": password},
            ),
            200,
            "Owner login",
        )["access_token"]
        customer = checked(
            gateway.post(
                "/api/v1/auth/login",
                json={"username": "h3customer", "password": password},
            ),
            200,
            "Customer login",
        )["access_token"]
        owner_auth = {"Authorization": f"Bearer {owner}"}
        customer_auth = {"Authorization": f"Bearer {customer}"}
        checked(gateway.get("/api/v1/auth/me", headers=customer_auth), 200, "Identity me")
        assert gateway.get("/api/v1/me/tickets").status_code == 401
        assert gateway.post("/api/v1/events", json={}).status_code == 422

        start = datetime.now(UTC) + timedelta(days=9)
        event = checked(
            gateway.post(
                "/api/v1/events",
                json={
                    "name": "H5 Gateway Stage I disposable event",
                    "description": "Independent three-service HTTP acceptance",
                    "venue": "Disposable fixture",
                    "start_at": start.isoformat(),
                    "end_at": (start + timedelta(hours=3)).isoformat(),
                },
                headers=owner_auth,
            ),
            201,
            "Owner draft creation",
        )
        event_id = str(UUID(event["id"]))
        assert event["status"] == "draft"
        assert gateway.get(f"/api/v1/events/{event_id}").status_code == 404

        zone = checked(
            gateway.post(
                f"/api/v1/events/{event_id}/zones",
                json={
                    "name": "General",
                    "mode": "general",
                    "price_minor": 2500,
                    "currency": "ARS",
                    "capacity": 2,
                    "seats": [],
                },
                headers=owner_auth,
            ),
            201,
            "Ticketing zone creation through Gateway",
        )
        zone_id = str(UUID(zone["id"]))
        assert zone["available"] == 2
        unauthorized = gateway.post(
            f"/api/v1/events/{event_id}/zones",
            json={
                "name": "Unauthorized",
                "mode": "general",
                "price_minor": 2500,
                "currency": "ARS",
                "capacity": 1,
            },
            headers=customer_auth,
        )
        assert unauthorized.status_code in {403, 404}, (
            f"Unauthorized zone creation: {unauthorized.status_code}"
        )

        publish_reply = gateway.post(
            f"/api/v1/events/{event_id}/publish",
            headers=owner_auth,
            json={},
        )
        published = checked(publish_reply, 200, "Publish through Gateway")
        assert published["status"] == "published"
        trace_id = publish_reply.headers.get("X-Request-ID", "")
        assert len(trace_id) == 32 and all(
            digit in "0123456789abcdef" for digit in trace_id
        ), "Expected NGINX-generated X-Request-ID in response"
        # CI correlates one publish command across all four process log streams.
        print(f"H5_PUBLISH_TRACE_ID={trace_id}", flush=True)
        assert checked(gateway.get(f"/api/v1/events/{event_id}"), 200, "Public event")["id"] == event_id
        catalog = checked(gateway.get("/api/v1/events"), 200, "Public catalog")
        assert any(item["id"] == event_id for item in catalog["items"])
        stock = checked(
            gateway.get(f"/api/v1/events/{event_id}/inventory"), 200, "Public inventory"
        )
        assert len(stock["zones"]) == 1 and stock["zones"][0]["available"] == 2

        purchase_body = {
            "event_id": event_id,
            "items": [{"zone_id": zone_id, "quantity": 1, "seat_ids": []}],
        }
        purchase_auth = customer_auth | {"Idempotency-Key": f"h5-{uuid4()}"}
        first_response = gateway.post(
            "/api/v1/orders", headers=purchase_auth, json=purchase_body,
        )
        order = checked(first_response, 201, "React purchase")
        assert first_response.headers["idempotent-replayed"] == "false"
        assert order["status"] == "confirmed"
        assert order["event_id"] == event_id
        assert len(order["tickets"]) == 1
        assert order["total_minor"] == 2500

        replay_response = gateway.post(
            "/api/v1/orders", headers=purchase_auth, json=purchase_body,
        )
        replay = checked(replay_response, 200, "React purchase replay")
        assert replay_response.headers["idempotent-replayed"] == "true"
        assert replay["id"] == order["id"]
        assert {t["id"] for t in replay["tickets"]} == {t["id"] for t in order["tickets"]}
        conflict = gateway.post(
            "/api/v1/orders",
            headers=purchase_auth,
            json={
                "event_id": event_id,
                "items": [{"zone_id": zone_id, "quantity": 2, "seat_ids": []}],
            },
        )
        assert conflict.status_code == 409
        remaining = checked(
            gateway.get(f"/api/v1/events/{event_id}/inventory"), 200, "Remaining stock"
        )
        assert remaining["zones"][0]["available"] == 1

        mine = checked(
            gateway.get("/api/v1/me/tickets", headers=customer_auth),
            200,
            "Customer tickets",
        )
        assert mine["total"] == 1
        assert mine["items"][0]["id"] == order["tickets"][0]["id"]
        assert gateway.get("/api/v1/me/tickets", headers=owner_auth).status_code == 403
        assert gateway.post(
            f"/api/v1/events/{event_id}/unpublish", headers=owner_auth, json={},
        ).status_code == 409
        assert gateway.get(f"/api/v1/events/{event_id}").status_code == 200

        logged_out = gateway.post("/api/v1/auth/logout", headers=customer_auth)
        assert logged_out.status_code == 204
        assert gateway.get("/api/v1/me/tickets", headers=customer_auth).status_code in {401, 403}

    print("PASS: Gateway H5 routes Identity, Events and Ticketing without Legacy")
    print("PASS: customer/owner authorization and inaccessible internal endpoints")
    print("PASS: create draft, zone, publish, catalog, inventory, buy and ticket list")
    print("PASS: repeat purchase replays one order, changed payload conflicts")
    print("PASS: confirmed order blocks unpublish; logout invalidates customer token")


if __name__ == "__main__":
    main()
