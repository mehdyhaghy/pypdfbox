from __future__ import annotations

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)


def test_compute_revision_number_from_version_v1_promotes_revision3_permissions() -> None:
    permissions = AccessPermission(0)
    permissions.set_can_fill_in_form(True)
    policy = StandardProtectionPolicy(permissions=permissions)
    handler = StandardSecurityHandler(policy)

    assert handler.compute_revision_number_from_version(1) == 3


def test_compute_revision_number_from_version_v1_keeps_revision2_permissions() -> None:
    permissions = AccessPermission(0)
    permissions.set_can_print(True)
    policy = StandardProtectionPolicy(permissions=permissions)
    handler = StandardSecurityHandler(policy)

    assert handler.compute_revision_number_from_version(1) == 2
