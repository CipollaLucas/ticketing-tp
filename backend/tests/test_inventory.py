from uuid import uuid4

import pytest
from test_events import actors as actors  # noqa: PLC0414
from test_events import create


def zone(**kw):
    return {"name": "Campo", "mode": "general", "capacity": 2,
            "price_minor": 1500, "currency": "ARS", **kw}


def add_zone(client, actors, eid, **kw):
    return client.post(f"/api/v1/events/{eid}/zones",
                       headers=actors["owner"][1], json=zone(**kw))


def test_inventory_modes_and_publication(client, actors):
    event = create(client, actors)
    eid = event["id"]
    general = add_zone(client, actors, eid)
    assert general.status_code == 201, general.text
    assert general.json()["available"] == 2
    numbered = add_zone(client, actors, eid, name="Platea", mode="numbered", capacity=None,
                        seats=[{"label": "A1"}, {"label": "A2"}])
    assert numbered.status_code == 201, numbered.text
    assert numbered.json()["available"] == 2
    assert len({s["id"] for s in numbered.json()["seats"]}) == 2
    path = f"/api/v1/events/{eid}/inventory"
    assert client.get(path).status_code == 404
    own = client.get(f"/api/v1/owner/events/{eid}/inventory", headers=actors["owner"][1])
    assert len(own.json()["zones"]) == 2
    assert client.post(f"/api/v1/events/{eid}/publish",
                       headers=actors["owner"][1], json={}).status_code == 200
    assert len(client.get(path).json()["zones"]) == 2
    assert add_zone(client, actors, eid, name="Extra").status_code == 409


@pytest.mark.parametrize("kw", [
    {"capacity": 0}, {"capacity": -1}, {"capacity": True}, {"capacity": 1.5},
    {"price_minor": 1.2}, {"price_minor": -1}, {"currency": "ZZZ"},
    {"currency": "ars"}, {"name": " "}, {"name": "bad\x00name"},
    {"seats": [{"label": "A1"}]}, {"available": 100}, {"event_id": str(uuid4())},
    {"mode": "numbered", "capacity": None, "seats": []},
    {"mode": "numbered", "capacity": None, "seats": [{"label": "A1"}]*2},
    {"mode": "numbered", "seats": [{"label": "A1"}]},
])
def test_inventory_invalid_atomic(client, actors, kw):
    eid = create(client, actors)["id"]
    assert add_zone(client, actors, eid, **kw).status_code == 422
    result = client.get(f"/api/v1/owner/events/{eid}/inventory", headers=actors["owner"][1])
    assert result.json()["zones"] == []


def test_inventory_roles_duplicates_and_missing(client, actors):
    eid = create(client, actors)["id"]
    path = f"/api/v1/events/{eid}/zones"
    for actor, code in [(None, 401), ("customer", 403), ("other", 403)]:
        assert client.post(path, json=zone(),
                           headers=actors[actor][1] if actor else {}).status_code == code
    assert client.post(path, json=zone(), headers=actors["admin"][1]).status_code == 201
    assert add_zone(client, actors, eid).status_code == 409
    assert add_zone(client, actors, str(uuid4())).status_code == 404
    assert client.get(f"/api/v1/owner/events/{eid}/inventory",
                      headers=actors["other"][1]).status_code == 403
