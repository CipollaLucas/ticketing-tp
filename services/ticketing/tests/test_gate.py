"""Pure transition and transactional port tests."""
from uuid import uuid4

import pytest

from ticketing_service.application import change_sale_gate
from ticketing_service.domain import GateCommand, GateConflict, GateState, next_gate


def command(event_id, action="open", expected_version=0, revision=1, command_id=None):
    return GateCommand(command_id or uuid4(), event_id, action, expected_version, revision)


class MemoryUnit:
    def __init__(self, event):
        self.state = GateState(event, "closed", 0, 0)
        self.commands = {}
        self.rollbacks = 0
        self.commits = 0

    def previous_command(self, value):
        return self.commands.get(value.command_id)

    def lock_gate(self, event_id):
        return self.state if self.state.event_id == event_id else None

    def save(self, value, state):
        self.state = state
        self.commands[value.command_id] = (value, state)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_gate_opens_and_closes_with_versions_and_command_replay():
    event = uuid4()
    unit = MemoryUnit(event)
    opened = command(event)
    result = change_sale_gate(opened, unit)
    assert result == GateState(event, "open", 1, 1)
    assert change_sale_gate(opened, unit) == result
    assert unit.commits == 1
    closed = command(event, action="close", expected_version=1, revision=1)
    assert change_sale_gate(closed, unit) == GateState(event, "closed", 2, 1)
    assert unit.commits == 2


@pytest.mark.parametrize("action,version,revision", [
    ("open", 1, 1), ("open", 0, 0), ("close", 0, 1),
    ("open", -1, 1), ("open", 0, -1),
])
def test_invalid_commands_preserve_gate(action, version, revision):
    event = uuid4()
    unit = MemoryUnit(event)
    with pytest.raises(GateConflict):
        change_sale_gate(command(event, action, version, revision), unit)
    assert unit.state == GateState(event, "closed", 0, 0)
    assert unit.commits == 0


def test_unknown_event_is_closed():
    unit = MemoryUnit(uuid4())
    with pytest.raises(GateConflict, match="Unknown"):
        change_sale_gate(command(uuid4()), unit)


def test_command_id_collision_denied_without_new_commit():
    event = uuid4()
    unit = MemoryUnit(event)
    first = command(event)
    change_sale_gate(first, unit)
    conflicting = command(event, "close", 1, 1, first.command_id)
    with pytest.raises(GateConflict, match="reused"):
        change_sale_gate(conflicting, unit)
    assert unit.commits == 1


def test_revision_cannot_reopen_with_old_metadata():
    event = uuid4()
    current = GateState(event, "closed", 2, 3)
    with pytest.raises(GateConflict, match="newer"):
        next_gate(current, command(event, "open", 2, 3))
