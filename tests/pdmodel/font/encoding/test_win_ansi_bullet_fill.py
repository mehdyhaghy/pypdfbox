"""Hand-written tests for ``WinAnsiEncoding`` bullet fill-in helpers.

Covers Wave 254 additions on :class:`WinAnsiEncoding`:

* ``BULLET_FILL_START`` — class constant for the inclusive lower bound of
  the spec-mandated bullet fall-back range.
* ``EXPLICIT_BULLET_CODE`` — the canonical ``bullet`` position from the
  upstream WinAnsi table (0o225).
* ``is_bullet_fill_code(code)`` — predicate distinguishing fall-back
  positions from the explicit bullet code and from explicitly mapped codes.
* ``get_bullet_fill_codes()`` — immutable set of the fall-back codes.
* ``is_explicit_code(code)`` — predicate matching the explicit-table
  membership (excludes ``.notdef`` low codes and the bullet fill-ins).
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding

# ---------- constants ------------------------------------------------------


def test_bullet_fill_start_is_octal_041():
    assert WinAnsiEncoding.BULLET_FILL_START == 0o41
    assert WinAnsiEncoding.BULLET_FILL_START == 33


def test_explicit_bullet_code_is_octal_225():
    assert WinAnsiEncoding.EXPLICIT_BULLET_CODE == 0o225
    assert WinAnsiEncoding.EXPLICIT_BULLET_CODE == 149


def test_explicit_bullet_code_resolves_to_bullet():
    enc = WinAnsiEncoding.INSTANCE
    assert enc.get_name(WinAnsiEncoding.EXPLICIT_BULLET_CODE) == "bullet"


def test_explicit_bullet_code_is_in_explicit_table():
    enc = WinAnsiEncoding.INSTANCE
    # The canonical bullet must be in the explicit WinAnsi table, not a
    # fall-back fill-in.
    assert enc.is_explicit_code(WinAnsiEncoding.EXPLICIT_BULLET_CODE) is True
    assert enc.is_bullet_fill_code(WinAnsiEncoding.EXPLICIT_BULLET_CODE) is False


# ---------- is_bullet_fill_code -------------------------------------------


def test_is_bullet_fill_code_true_for_known_fill_in_codes():
    enc = WinAnsiEncoding.INSTANCE
    # 0x81, 0x8D, 0x8F, 0x90, 0x9D — gaps in CP1252 that PDFBox fills with
    # bullet (verified by test_win_ansi_encoding::test_unmapped_high_codes_*).
    for code in (0x81, 0x8D, 0x8F, 0x90, 0x9D):
        assert enc.is_bullet_fill_code(code) is True, f"{code:#x} should be a fill-in"


def test_is_bullet_fill_code_false_for_low_codes():
    # Codes <= 0o40 are below BULLET_FILL_START — not eligible for the
    # bullet fall-back.
    enc = WinAnsiEncoding.INSTANCE
    for code in (0x00, 0x01, 0x1F, 0o40):
        assert enc.is_bullet_fill_code(code) is False


def test_is_bullet_fill_code_false_for_explicitly_mapped_letters():
    enc = WinAnsiEncoding.INSTANCE
    for code in (ord("A"), ord("Z"), ord("a"), ord("z"), ord("0")):
        assert enc.is_bullet_fill_code(code) is False


def test_is_bullet_fill_code_false_for_canonical_bullet():
    # The explicit /bullet at 0o225 is *not* a fill-in.
    enc = WinAnsiEncoding.INSTANCE
    assert enc.is_bullet_fill_code(WinAnsiEncoding.EXPLICIT_BULLET_CODE) is False


def test_is_bullet_fill_code_false_for_out_of_range():
    # Out-of-range codes never participate in the fill-in.
    enc = WinAnsiEncoding.INSTANCE
    assert enc.is_bullet_fill_code(-1) is False
    assert enc.is_bullet_fill_code(256) is False
    assert enc.is_bullet_fill_code(1024) is False


# ---------- get_bullet_fill_codes -----------------------------------------


def test_get_bullet_fill_codes_returns_frozenset():
    fills = WinAnsiEncoding.INSTANCE.get_bullet_fill_codes()
    assert isinstance(fills, frozenset)


def test_get_bullet_fill_codes_excludes_explicit_bullet():
    fills = WinAnsiEncoding.INSTANCE.get_bullet_fill_codes()
    assert WinAnsiEncoding.EXPLICIT_BULLET_CODE not in fills


def test_get_bullet_fill_codes_includes_known_gap_codes():
    fills = WinAnsiEncoding.INSTANCE.get_bullet_fill_codes()
    for code in (0x81, 0x8D, 0x8F, 0x90, 0x9D):
        assert code in fills


def test_get_bullet_fill_codes_all_resolve_to_bullet():
    enc = WinAnsiEncoding.INSTANCE
    fills = enc.get_bullet_fill_codes()
    for code in fills:
        assert enc.get_name(code) == "bullet"


def test_get_bullet_fill_codes_within_range():
    enc = WinAnsiEncoding.INSTANCE
    for code in enc.get_bullet_fill_codes():
        assert WinAnsiEncoding.BULLET_FILL_START <= code < 256


def test_get_bullet_fill_codes_is_immutable():
    # frozenset has no add(); attempting an in-place mutation raises.
    fills = WinAnsiEncoding.INSTANCE.get_bullet_fill_codes()
    with pytest.raises(AttributeError):
        fills.add(0x42)  # type: ignore[attr-defined]


def test_get_bullet_fill_codes_partition_with_explicit_codes():
    # For every code in BULLET_FILL_START..255 the encoding has a mapping;
    # each such code is either a fill-in or in the explicit table — never
    # both, never neither.
    enc = WinAnsiEncoding.INSTANCE
    fills = enc.get_bullet_fill_codes()
    for code in range(WinAnsiEncoding.BULLET_FILL_START, 256):
        is_fill = code in fills
        is_explicit = enc.is_explicit_code(code)
        assert is_fill ^ is_explicit, f"code {code:#x} ambiguous"


def test_get_bullet_fill_codes_count_consistent_with_get_codes_for_name():
    # All bullet codes = 1 explicit + N fill-ins.
    enc = WinAnsiEncoding.INSTANCE
    all_bullets = enc.get_codes_for_name("bullet")
    fills = enc.get_bullet_fill_codes()
    assert len(all_bullets) == len(fills) + 1


# ---------- is_explicit_code ----------------------------------------------


def test_is_explicit_code_true_for_letters():
    enc = WinAnsiEncoding.INSTANCE
    for code in (ord("A"), ord("Z"), ord("a"), ord("z")):
        assert enc.is_explicit_code(code) is True


def test_is_explicit_code_true_for_extended_glyphs():
    enc = WinAnsiEncoding.INSTANCE
    # Euro and copyright are explicit table entries.
    assert enc.is_explicit_code(0x80) is True   # Euro
    assert enc.is_explicit_code(0xA9) is True   # copyright


def test_is_explicit_code_false_for_unmapped_low_code():
    # 0x01 is below BULLET_FILL_START and never mapped — not in the
    # explicit table.
    enc = WinAnsiEncoding.INSTANCE
    assert enc.is_explicit_code(0x01) is False


def test_is_explicit_code_false_for_fill_in_code():
    enc = WinAnsiEncoding.INSTANCE
    assert enc.is_explicit_code(0x81) is False


def test_is_explicit_code_true_for_canonical_bullet():
    enc = WinAnsiEncoding.INSTANCE
    assert enc.is_explicit_code(WinAnsiEncoding.EXPLICIT_BULLET_CODE) is True


def test_is_explicit_code_false_for_out_of_range():
    enc = WinAnsiEncoding.INSTANCE
    assert enc.is_explicit_code(-1) is False
    assert enc.is_explicit_code(256) is False


# ---------- cross-helper invariants ---------------------------------------


def test_explicit_codes_plus_fill_codes_cover_high_range():
    # Every code in BULLET_FILL_START..255 is either explicit or a fill-in.
    enc = WinAnsiEncoding.INSTANCE
    for code in range(WinAnsiEncoding.BULLET_FILL_START, 256):
        assert enc.is_explicit_code(code) or enc.is_bullet_fill_code(code)


def test_no_overlap_between_explicit_and_fill_codes():
    enc = WinAnsiEncoding.INSTANCE
    for code in range(256):
        assert not (enc.is_explicit_code(code) and enc.is_bullet_fill_code(code))


def test_size_unchanged_by_new_helpers():
    # The fill-in tracking is bookkeeping only — code count stays at 224
    # (matches test_encoding_predicates::test_size_winansi_is_224_after_bullet_fillin).
    assert WinAnsiEncoding.INSTANCE.size() == 224
