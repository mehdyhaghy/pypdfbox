from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption import AccessPermission
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission as AP


# ---------- construction ----------


def test_default_constructor_grants_full_access() -> None:
    p = AP()
    assert p.is_owner_permission()
    assert p.can_print()
    assert p.can_modify()
    assert p.can_extract_content()
    assert p.can_modify_annotations()
    assert p.can_fill_in_form()
    assert p.can_extract_for_accessibility()
    assert p.can_assemble_document()
    assert p.can_print_faithful()
    assert p.can_print_degraded()  # alias


def test_constructor_minus_one_equivalent_to_no_arg() -> None:
    assert AP(-1).get_permission_bytes() == AP().get_permission_bytes()


def test_constructor_zero_revokes_all_defined_bits() -> None:
    p = AP(0)
    assert not p.can_print()
    assert not p.can_modify()
    assert not p.can_extract_content()
    assert not p.can_modify_annotations()
    assert not p.can_fill_in_form()
    assert not p.can_extract_for_accessibility()
    assert not p.can_assemble_document()
    assert not p.can_print_faithful()
    assert not p.is_owner_permission()


def test_constructor_decodes_individual_bit() -> None:
    # Only bit 3 (printable) set
    p = AP(1 << 2)
    assert p.can_print()
    assert not p.can_modify()
    assert not p.can_extract_content()


def test_get_instance_returns_owner_perms() -> None:
    p = AP.get_instance()
    assert p.is_owner_permission()
    assert isinstance(p, AP)


def test_get_owner_access_permission_returns_owner_perms() -> None:
    p = AP.get_owner_access_permission()
    assert p.is_owner_permission()


# ---------- bit positions match the PDF spec ----------


@pytest.mark.parametrize(
    ("bit_pos", "getter_name", "setter_name"),
    [
        (3, "can_print", "set_can_print"),
        (4, "can_modify", "set_can_modify"),
        (5, "can_extract_content", "set_can_extract_content"),
        (6, "can_modify_annotations", "set_can_modify_annotations"),
        (9, "can_fill_in_form", "set_can_fill_in_form"),
        (10, "can_extract_for_accessibility", "set_can_extract_for_accessibility"),
        (11, "can_assemble_document", "set_can_assemble_document"),
        (12, "can_print_faithful", "set_can_print_faithful"),
        (12, "can_print_degraded", "set_can_print_degraded"),
    ],
)
def test_bit_positions_match_spec(
    bit_pos: int, getter_name: str, setter_name: str
) -> None:
    """Setter on a fresh-zero instance flips exactly the spec-mandated bit."""
    p = AP(0)
    expected_mask = 1 << (bit_pos - 1)

    getattr(p, setter_name)(True)
    assert p.get_permission_bytes() == expected_mask
    assert getattr(p, getter_name)() is True

    getattr(p, setter_name)(False)
    assert p.get_permission_bytes() == 0
    assert getattr(p, getter_name)() is False


def test_bit_position_constants() -> None:
    assert AP.BIT_PRINTABLE == 3
    assert AP.BIT_MODIFIABLE == 4
    assert AP.BIT_EXTRACTABLE == 5
    assert AP.BIT_MODIFIABLE_ANNOTATIONS == 6
    assert AP.BIT_FILL_FORMS == 9
    assert AP.BIT_EXTRACTABLE_FOR_ACCESSIBILITY == 10
    assert AP.BIT_ASSEMBLE_DOCUMENT == 11
    assert AP.BIT_PRINT_DEGRADED == 12


# ---------- read-only freezing ----------


def test_set_read_only_blocks_subsequent_setters() -> None:
    p = AP(0)
    p.set_read_only()
    assert p.is_read_only()

    # Every setter must become a no-op.
    p.set_can_print(True)
    p.set_can_modify(True)
    p.set_can_extract_content(True)
    p.set_can_modify_annotations(True)
    p.set_can_fill_in_form(True)
    p.set_can_extract_for_accessibility(True)
    p.set_can_assemble_document(True)
    p.set_can_print_faithful(True)
    p.set_can_print_degraded(True)

    assert p.get_permission_bytes() == 0
    assert not p.can_print()
    assert not p.can_modify()


def test_read_only_default_false() -> None:
    p = AP()
    assert not p.is_read_only()


# ---------- owner predicate ----------


def test_is_owner_permission_requires_every_defined_bit() -> None:
    p = AP()
    assert p.is_owner_permission()
    p.set_can_modify(False)
    assert not p.is_owner_permission()


# ---------- get_permission_bytes / get_permission_bits_as_int ----------


def test_get_permission_bytes_round_trips() -> None:
    p = AP(0)
    p.set_can_print(True)
    p.set_can_modify(True)
    out = p.get_permission_bytes()
    decoded = AP(out)
    assert decoded.can_print()
    assert decoded.can_modify()
    assert not decoded.can_extract_content()


def test_get_permission_bits_as_int_alias() -> None:
    p = AP(0xABCD)
    assert p.get_permission_bits_as_int() == p.get_permission_bytes() == 0xABCD


def test_default_permissions_value_is_negated_three() -> None:
    """Upstream spec: ``DEFAULT_PERMISSIONS = ~3`` (all defined bits set,
    bits 1 and 2 cleared in the spec sense; in two's complement Python
    sees this as ``-4``)."""
    assert AP().get_permission_bytes() == ~3 == -4


# ---------- per-bit independence ----------


def test_setting_one_bit_does_not_disturb_others() -> None:
    p = AP(0)
    p.set_can_print(True)
    p.set_can_assemble_document(True)
    p.set_can_print(False)
    assert not p.can_print()
    assert p.can_assemble_document()


# ---------- module-level re-export ----------


def test_reexport_from_package() -> None:
    assert AccessPermission is AP
