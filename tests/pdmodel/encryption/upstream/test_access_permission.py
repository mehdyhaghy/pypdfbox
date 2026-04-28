"""Ported from upstream PDFBox tests for ``AccessPermission``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/encryption/`` —
upstream coverage for ``AccessPermission`` is minimal (it lives largely
in ``TestSymmetricKeyEncryption`` / ``TestAllSecurityHandlers`` parity
suites). The targeted assertions translated below mirror the small
direct-API checks PDFBox runs on the class plus the canonical default /
read-only / per-bit toggle behaviour exercised throughout the upstream
encryption tests.
"""

from __future__ import annotations

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission


# Translated from default-constructor checks scattered across the
# upstream encryption test suites:
#   AccessPermission ap = new AccessPermission();
#   assertTrue(ap.canAssembleDocument());
#   assertTrue(ap.canExtractContent());
#   ... etc.
def test_default_constructor_grants_full_permissions() -> None:
    ap = AccessPermission()
    assert ap.can_assemble_document()
    assert ap.can_extract_content()
    assert ap.can_extract_for_accessibility()
    assert ap.can_fill_in_form()
    assert ap.can_modify()
    assert ap.can_modify_annotations()
    assert ap.can_print()
    assert ap.can_print_faithful()
    assert ap.is_owner_permission()


# Translated from `assertEquals(~3, new AccessPermission().getPermissionBytes())`.
def test_default_permission_bytes_is_negated_three() -> None:
    assert AccessPermission().get_permission_bytes() == ~3


# Translated from upstream `getInstance` smoke test:
#   AccessPermission ap = AccessPermission.getInstance();
#   assertTrue(ap.isOwnerPermission());
def test_get_instance_returns_owner() -> None:
    assert AccessPermission.get_instance().is_owner_permission()


# Translated from the read-only enforcement check in
# `TestSymmetricKeyEncryption` (after a document is opened the perm
# object is frozen, mutations must be silently dropped).
def test_set_read_only_silences_setters() -> None:
    ap = AccessPermission()
    ap.set_read_only()
    assert ap.is_read_only()
    before = ap.get_permission_bytes()
    ap.set_can_print(False)
    ap.set_can_modify(False)
    ap.set_can_extract_content(False)
    ap.set_can_modify_annotations(False)
    ap.set_can_fill_in_form(False)
    ap.set_can_extract_for_accessibility(False)
    ap.set_can_assemble_document(False)
    ap.set_can_print_faithful(False)
    assert ap.get_permission_bytes() == before


# Translated from upstream per-bit `setCanX(false); assertFalse(canX())`
# parametrised pattern.
def test_each_setter_clears_only_its_own_bit() -> None:
    cases = [
        ("set_can_print", "can_print", 1 << 2),
        ("set_can_modify", "can_modify", 1 << 3),
        ("set_can_extract_content", "can_extract_content", 1 << 4),
        ("set_can_modify_annotations", "can_modify_annotations", 1 << 5),
        ("set_can_fill_in_form", "can_fill_in_form", 1 << 8),
        (
            "set_can_extract_for_accessibility",
            "can_extract_for_accessibility",
            1 << 9,
        ),
        ("set_can_assemble_document", "can_assemble_document", 1 << 10),
        ("set_can_print_faithful", "can_print_faithful", 1 << 11),
    ]
    for setter, getter, mask in cases:
        ap = AccessPermission()
        before = ap.get_permission_bytes()
        getattr(ap, setter)(False)
        assert not getattr(ap, getter)()
        # Exactly that one bit got turned off.
        assert ap.get_permission_bytes() == before & ~mask


# Translated from `AccessPermission(int)` round-trip used in
# `StandardSecurityHandler.prepareForDecryption` parity tests.
def test_int_constructor_round_trips_through_get_permission_bytes() -> None:
    for value in (0, 1, ~3, 0xFFFC, -4, -44):
        assert AccessPermission(value).get_permission_bytes() == value


# `canPrintFaithful` and the legacy `canPrintDegraded` alias must agree —
# upstream renamed the method but kept the old name on the public API.
def test_can_print_faithful_alias() -> None:
    ap = AccessPermission(0)
    ap.set_can_print_faithful(True)
    assert ap.can_print_degraded()
    ap.set_can_print_degraded(False)
    assert not ap.can_print_faithful()
