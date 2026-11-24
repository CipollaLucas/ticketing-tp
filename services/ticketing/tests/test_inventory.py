"""Pure inventory rules preserve the Legacy zone/seat contract."""
from uuid import uuid4

import pytest

from ticketing_service.inventory import SeatSpec, ZoneSpec, validate_seat, validate_zone


def zone(**changes):
    data = {
        "id": uuid4(), "event_id": uuid4(), "name": "General",
        "mode": "general", "price_minor": 1500, "currency": "ARS",
        "capacity": 120, "available": 120,
    }
    return ZoneSpec(**(data | changes))


@pytest.mark.parametrize("value", [
    zone(), zone(mode="numbered", capacity=None, available=None),
    zone(mode="general", available=0), zone(mode="general", available=119),
])
def test_valid_zone(value):
    validate_zone(value)


@pytest.mark.parametrize("value", [
    zone(name=" "), zone(name="a" * 101), zone(price_minor=-1),
    zone(currency="XXX"), zone(capacity=0), zone(available=121),
    zone(mode="numbered"), zone(mode="numbered", capacity=None, available=1),
])
def test_invalid_zone(value):
    with pytest.raises(ValueError):
        validate_zone(value)


def test_seat_label():
    validate_seat(SeatSpec(uuid4(), uuid4(), "A-01"))
    with pytest.raises(ValueError):
        validate_seat(SeatSpec(uuid4(), uuid4(), " "))
