"""Provision use case: closed-only, idempotent, atomic failure behavior."""

from uuid import uuid4

import pytest

from ticketing_service.domain import GateState
from ticketing_service.provision import provision_closed_gate


class FakeProvision:
    def __init__(self):
        self.values = {}
        self.committed = 0
        self.rolled_back = 0
        self.fail = False

    def ensure_closed_gate(self, event_id):
        if self.fail:
            raise RuntimeError("Database failure")
        return self.values.setdefault(event_id, GateState(event_id, "closed", 0, 0))

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def test_initial_gate_is_closed_and_duplicate_does_not_reset_version():
    event = uuid4()
    unit = FakeProvision()
    first = provision_closed_gate(event, unit)
    assert first == GateState(event, "closed", 0, 0)
    unit.values[event] = GateState(event, "open", 5, 9)
    again = provision_closed_gate(event, unit)
    assert again == GateState(event, "open", 5, 9)
    assert unit.committed == 2


def test_failure_rolls_back():
    unit = FakeProvision()
    unit.fail = True
    with pytest.raises(RuntimeError):
        provision_closed_gate(uuid4(), unit)
    assert unit.rolled_back == 1 and unit.committed == 0
