"""Use-case tests proving infrastructure-free inventory orchestration."""
from uuid import uuid4

import pytest

from app.ticketing_core.application.inventory import (
    InventoryView,
    ZoneCommand,
    ZoneView,
    configure_zone,
    view_inventory,
)


class FakeInventory:
    def __init__(self, fail=False):
        self.calls = []
        self.zone_id = uuid4()
        self.fail = fail

    def add_zone(self, event_id, actor_id, command):
        self.calls.append("add")
        if self.fail:
            raise ValueError("invalid state")
        return self.zone_id

    def read_zone(self, zone_id):
        self.calls.append("zone")
        return ZoneView(zone_id, "General", "general", 150000, "ARS", 2, 2, ())

    def read_inventory(self, event_id, actor_id):
        self.calls.append("inventory")
        return InventoryView(event_id, ())

    def commit(self):
        self.calls.append("commit")

    def rollback(self):
        self.calls.append("rollback")


def test_configure_zone_commits_before_reading_receipt():
    adapter = FakeInventory()
    cmd = ZoneCommand("General", "general", 150000, "ARS", 2, ())
    zone = configure_zone(uuid4(), uuid4(), cmd, adapter)
    assert zone.available == 2
    assert adapter.calls == ["add", "commit", "zone"]


def test_configure_zone_rolls_back_on_failure():
    adapter = FakeInventory(fail=True)
    with pytest.raises(ValueError):
        configure_zone(uuid4(), uuid4(), ZoneCommand("G", "general", 0, "ARS", 1, ()), adapter)
    assert adapter.calls == ["add", "rollback"]


def test_read_inventory_does_not_write():
    adapter = FakeInventory()
    assert not view_inventory(uuid4(), None, adapter).zones
    assert adapter.calls == ["inventory"]
