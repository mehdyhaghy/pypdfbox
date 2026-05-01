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


# ---------- byte-array constructor (from_bytes) ----------


def test_from_bytes_decodes_big_endian_signed_int() -> None:
    """Mirrors upstream ``AccessPermission(byte[] b)`` — bytes are MSB-first
    and the resulting int is signed (so a leading 0xFF stays negative)."""
    # ~3 == 0xFFFFFFFC, big-endian signed → bytes [0xFF, 0xFF, 0xFF, 0xFC].
    p = AP.from_bytes(b"\xff\xff\xff\xfc")
    assert p.get_permission_bytes() == ~3
    assert p.is_owner_permission()


def test_from_bytes_zeroed_buffer_revokes_everything() -> None:
    p = AP.from_bytes(b"\x00\x00\x00\x00")
    assert p.get_permission_bytes() == 0
    assert not p.can_print()
    assert not p.is_owner_permission()


def test_from_bytes_short_buffer_raises() -> None:
    with pytest.raises(ValueError):
        AP.from_bytes(b"\x00\x00\x00")


def test_from_bytes_only_print_bit() -> None:
    # Only bit 3 (printable) set → 0x00000004
    p = AP.from_bytes(b"\x00\x00\x00\x04")
    assert p.can_print()
    assert not p.can_modify()


# ---------- get_permission_bytes_for_public_key ----------


def test_get_permission_bytes_for_public_key_sets_bit_1_clears_7_8_and_high() -> None:
    """Upstream public-key flavour: bit 1 ON, bits 7+8 OFF, bits 13..32 OFF.

    Starting from owner perms (-4 = 0xFFFFFFFC), the result must end up
    equal to 0xFFD & ~0x60 == 0xF9D (bits 1, 3, 4, 5, 6, 9, 10, 11, 12 set).
    """
    p = AP()  # owner / -4
    out = p.get_permission_bytes_for_public_key()
    expected = (1 << 0) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5) \
        | (1 << 8) | (1 << 9) | (1 << 10) | (1 << 11)
    assert out == expected
    # Mutates in-place — subsequent get_permission_bytes returns the same.
    assert p.get_permission_bytes() == expected


def test_get_permission_bytes_for_public_key_from_zero() -> None:
    p = AP(0)
    out = p.get_permission_bytes_for_public_key()
    # Only bit 1 is set; bits 7, 8, and 13..32 are all already zero.
    assert out == 1


def test_get_permission_bytes_for_public_key_clears_high_bits() -> None:
    # 0xFFFFFFFE — every bit except bit 1 (1-based) set. The helper must
    # reinstate bit 1, clear bits 7 and 8, and clear everything above bit 12.
    p = AP(-2)
    out = p.get_permission_bytes_for_public_key()
    # Bits remaining: 1..6, 9..12 → 0x0F3F.
    assert out == 0x0F3F


# ---------- has_any_revision3_permission_set ----------


def test_has_any_revision3_permission_set_owner() -> None:
    assert AP().has_any_revision3_permission_set()


def test_has_any_revision3_permission_set_zero() -> None:
    assert not AP(0).has_any_revision3_permission_set()


@pytest.mark.parametrize(
    "setter",
    [
        "set_can_fill_in_form",
        "set_can_extract_for_accessibility",
        "set_can_assemble_document",
        "set_can_print_faithful",
    ],
)
def test_has_any_revision3_permission_set_each_r3_bit(setter: str) -> None:
    p = AP(0)
    getattr(p, setter)(True)
    assert p.has_any_revision3_permission_set()


@pytest.mark.parametrize(
    "setter",
    [
        "set_can_print",
        "set_can_modify",
        "set_can_extract_content",
        "set_can_modify_annotations",
    ],
)
def test_has_any_revision3_permission_set_ignores_r2_bits(setter: str) -> None:
    p = AP(0)
    getattr(p, setter)(True)
    assert not p.has_any_revision3_permission_set()
