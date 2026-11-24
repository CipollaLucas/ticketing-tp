"""Pure Identity policies without database or FastAPI."""
from uuid import uuid4

import pytest

from identity.domain.model import (
    IdentityFault,
    Principal,
    Role,
    ensure_owner,
    validate_role_change,
)


def test_admin_and_owner_permissions():
    owner = Principal(uuid4(), "owner", "Owner", Role.EVENT_OWNER)
    admin = Principal(uuid4(), "admin", "Admin", Role.ADMINISTRATOR)
    outsider = uuid4()
    ensure_owner(owner, owner.id)
    ensure_owner(admin, outsider)
    with pytest.raises(IdentityFault) as failed:
        ensure_owner(owner, outsider)
    assert failed.value.status == 403


def test_role_change_prevents_self_demote():
    admin = Principal(uuid4(), "admin", "Admin", Role.ADMINISTRATOR)
    validate_role_change(admin, uuid4())
    with pytest.raises(IdentityFault) as failed:
        validate_role_change(admin, admin.id)
    assert failed.value.status == 409
