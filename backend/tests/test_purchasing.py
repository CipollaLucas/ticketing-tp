from uuid import UUID, uuid4

import pytest
from sqlalchemy import event as sql_event
from sqlalchemy import select
from test_events import actors as actors  # noqa: PLC0414
from test_events import create
from test_inventory import add_zone

from app.models import Event


def setup_sale(client, actors, *, capacity=2):
    eid = create(client, actors)["id"]
    general = add_zone(client, actors, eid, capacity=capacity).json()
    numbered = add_zone(client, actors, eid, name="Platea", mode="numbered", capacity=None,
                        seats=[{"label": "A1"}, {"label": "A2"}]).json()
    assert client.post(f"/api/v1/events/{eid}/publish", headers=actors["owner"][1],
                       json={}).status_code == 200
    return eid, general, numbered


def buy(client, actors, eid, items, key="purchase-1", actor="customer"):
    return client.post("/api/v1/orders", headers={**actors[actor][1], "Idempotency-Key": key},
                       json={"event_id": eid, "items": items})


def test_purchase_mixed_replay_price_and_privacy(client, actors):
    eid, general, numbered = setup_sale(client, actors)
    items = [{"zone_id": general["id"], "quantity": 2},
             {"zone_id": numbered["id"], "quantity": 1,
              "seat_ids": [numbered["seats"][0]["id"]]}]
    response = buy(client, actors, eid, items)
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["total_minor"] == 4500 and order["currency"] == "ARS"
    assert order["customer_id"] == str(actors["customer"][0])
    assert len(order["tickets"]) == 3
    assert len({t["id"] for t in order["tickets"]}) == 3
    assert "idempotency_key" not in order and "request_hash" not in order
    replay = buy(client, actors, eid, list(reversed(items)))
    assert replay.status_code == 200 and replay.json() == order
    assert replay.headers["idempotent-replayed"] == "true"
    assert buy(client, actors, eid, items[:1]).status_code == 409
    inv = client.get(f"/api/v1/events/{eid}/inventory").json()
    zones = {z["id"]: z for z in inv["zones"]}
    assert zones[general["id"]]["available"] == 0
    assert zones[numbered["id"]]["available"] == 1
    assert sum(s["available"] for s in zones[numbered["id"]]["seats"]) == 1
    path = f"/api/v1/orders/{order['id']}"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=actors["other"][1]).status_code == 403
    assert client.get(path, headers=actors["admin"][1]).json() == order
    assert client.get(path, headers=actors["customer"][1]).json() == order
    page = client.get("/api/v1/me/tickets?limit=2&offset=1",
                      headers=actors["customer"][1]).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert client.get("/api/v1/me/tickets", headers=actors["other"][1]).json()["total"] == 0
    assert client.post(f"/api/v1/events/{eid}/unpublish",
                       headers=actors["owner"][1], json={}).status_code == 409


@pytest.mark.parametrize("numbered", [False, True])
def test_no_double_sale_and_failed_multiitem_atomic(client, actors, numbered):
    eid, general, seats = setup_sale(client, actors, capacity=1)
    item = {"zone_id": seats["id"], "quantity": 1,
            "seat_ids": [seats["seats"][0]["id"]]} if numbered else {
                "zone_id": general["id"], "quantity": 1}
    assert buy(client, actors, eid, [item]).status_code == 201
    assert buy(client, actors, eid, [item], key="again").status_code == 409
    other = {"zone_id": general["id"], "quantity": 1} if numbered else {
        "zone_id": seats["id"], "quantity": 1, "seat_ids": [seats["seats"][0]["id"]]}
    assert buy(client, actors, eid, [other, item], key="multi").status_code == 409
    assert buy(client, actors, eid, [other], key="multi").status_code == 201


@pytest.mark.parametrize("change", [
    {"quantity": 0}, {"quantity": True}, {"quantity": 1.5}, {"quantity": 101},
    {"price_minor": 1}, {"seat_ids": [str(uuid4())]}, {"zone_id": str(uuid4())},
])
def test_invalid_purchase(client, actors, change):
    eid, general, _ = setup_sale(client, actors)
    result = buy(client, actors, eid, [{"zone_id": general["id"], "quantity": 1, **change}])
    assert result.status_code in (404, 422)
    assert client.get("/api/v1/me/tickets", headers=actors["customer"][1]).json()["total"] == 0


def test_purchase_auth_key_event_and_seat_rules(client, actors, db):
    eid, general, numbered = setup_sale(client, actors)
    item = {"zone_id": general["id"], "quantity": 1}
    payload = {"event_id": eid, "items": [item]}
    assert client.post("/api/v1/orders", json=payload).status_code == 401
    assert client.post("/api/v1/orders", json=payload,
                       headers=actors["customer"][1]).status_code == 422
    for key in ["", " ", "a"*129]:
        assert buy(client, actors, eid, [item], key=key).status_code == 422
    for actor in ["owner", "admin"]:
        assert buy(client, actors, eid, [item], actor=actor).status_code == 403
    for items in [[], [item, item], [{"zone_id": numbered["id"], "quantity": 1}],
                  [{"zone_id": numbered["id"], "quantity": 2,
                    "seat_ids": [numbered["seats"][0]["id"]]*2}]]:
        assert buy(client, actors, eid, items).status_code == 422
    assert buy(client, actors, str(uuid4()), [item]).status_code == 404
    event = db.get(Event, UUID(eid))
    event.status = "draft"
    db.commit()
    assert buy(client, actors, eid, [item]).status_code == 409


def test_rollback_injected_after_stock_then_retry(client, actors, db):
    from app.models import Order, Ticket, Zone

    eid, general, _ = setup_sale(client, actors)
    items = [{"zone_id": general["id"], "quantity": 1}]

    def fail_ticket(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO TICKETS"):
            raise RuntimeError("Injected ticket failure")

    engine = db.get_bind()
    sql_event.listen(engine, "before_cursor_execute", fail_ticket)
    try:
        with pytest.raises(RuntimeError, match="Injected ticket failure"):
            buy(client, actors, eid, items)
    finally:
        sql_event.remove(engine, "before_cursor_execute", fail_ticket)
    assert db.get(Zone, UUID(general["id"])).available == 2
    assert db.scalars(select(Order)).all() == []
    assert db.scalars(select(Ticket)).all() == []
    assert buy(client, actors, eid, items).status_code == 201


def test_currency_cross_event_and_past_rules(client, actors, db):
    from datetime import UTC, datetime, timedelta

    from app.models import Zone

    eid, general, numbered = setup_sale(client, actors)
    other_eid = create(client, actors)["id"]
    foreign = add_zone(client, actors, other_eid).json()
    item = {"zone_id": general["id"], "quantity": 1}
    assert buy(client, actors, eid, [{"zone_id": foreign["id"], "quantity": 1}]).status_code == 404
    assert buy(client, actors, eid, [{"zone_id": numbered["id"], "quantity": 1,
                                     "seat_ids": [str(uuid4())]}]).status_code == 422
    db.get(Zone, UUID(numbered["id"])).currency = "USD"
    db.commit()
    assert buy(client, actors, eid, [item, {"zone_id": numbered["id"], "quantity": 1,
                       "seat_ids": [numbered["seats"][0]["id"]]}]).status_code == 422
    assert db.get(Zone, UUID(general["id"])).available == 2
    result = buy(client, actors, eid, [item])
    assert result.status_code == 201
    stored = db.get(Event, UUID(eid))
    stored.start_at = datetime.now(UTC) - timedelta(hours=1)
    stored.end_at = datetime.now(UTC) + timedelta(hours=1)
    db.commit()
    assert buy(client, actors, eid, [item]).json() == result.json()
    assert buy(client, actors, eid, [item], key="past").status_code == 409


def test_canonical_seats_and_key_scoped_by_customer(client, actors, db):
    from app.models import Role, User

    eid, general, numbered = setup_sale(client, actors)
    item = {"zone_id": numbered["id"], "quantity": 2,
            "seat_ids": [s["id"] for s in numbered["seats"]]}
    result = buy(client, actors, eid, [item])
    assert result.status_code == 201
    item["seat_ids"].reverse()
    assert buy(client, actors, eid, [item]).json() == result.json()
    other = db.get(User, actors["other"][0])
    other.role = Role.CUSTOMER.value
    db.commit()
    assert buy(client, actors, eid, [{"zone_id": general["id"], "quantity": 1}],
               actor="other").status_code == 201
    for query in ["limit=0", "limit=101", "offset=-1"]:
        assert client.get("/api/v1/me/tickets?" + query,
                          headers=actors["customer"][1]).status_code == 422
    assert client.get(f"/api/v1/orders/{uuid4()}",
                      headers=actors["customer"][1]).status_code == 404
