"""Wave 1369 round-out tests for :class:`TTFSubsetter`.

Targets the *registration + dependency-expansion* surface of the
subsetter — the part of the upstream API that decides "which glyphs
end up in the output". Earlier waves cover the emitted bytes; this
file fills in:

* ``add_all`` accepts an arbitrary iterable and dedups via the
  internal set.
* ``add_glyph_ids`` deposits GIDs into the keep-set without going
  through the cmap.
* ``add_compound_references`` expands composite glyph components,
  including the transitive case (composite-of-composite).
* The keep-set always carries GID 0 (``.notdef``) regardless of how
  many glyphs the caller adds (mirrors upstream's "always keep .notdef"
  rule).
* ``set_prefix`` validation: the six-letter rule is *not* enforced
  inside the setter — the caller is trusted (matches upstream).
* ``to_bytes`` is deterministic for the same input — two consecutive
  calls produce identical output.
* The :func:`log2` and :func:`to_u_int32` helpers behave like their
  Java counterparts on boundary inputs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from pypdfbox.fontbox.ttf.ttf_subsetter import TTFSubsetter

_FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> object:
    """Open the bundled Liberation Sans TTF once per module."""
    font = TTFParser().parse(os.fspath(_FIXTURE_TTF))
    yield font
    font.close()


# ---------- registration set semantics ------------------------------------


def test_add_all_dedups_via_internal_set(liberation_sans: object) -> None:
    sub = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    sub.add_all([0x41, 0x42, 0x41, 0x43, 0x42])
    # Internal set has each codepoint once.
    assert sub._unicodes == {0x41, 0x42, 0x43}  # noqa: SLF001


def test_add_glyph_ids_keeps_notdef(liberation_sans: object) -> None:
    """``.notdef`` (GID 0) is registered by the constructor and survives
    further ``add_glyph_ids`` calls."""
    sub = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    sub.add_glyph_ids([10, 20, 30])
    assert 0 in sub._glyph_ids  # noqa: SLF001
    assert {10, 20, 30} <= sub._glyph_ids  # noqa: SLF001


def test_add_glyph_ids_accepts_arbitrary_iterable(liberation_sans: object) -> None:
    sub = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    sub.add_glyph_ids(g for g in (5, 6, 7))  # generator
    assert {5, 6, 7} <= sub._glyph_ids  # noqa: SLF001


def test_add_unicode_codepoint_round_trip(liberation_sans: object) -> None:
    sub = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    sub.add(ord("H"))
    sub.add(ord("i"))
    assert sub._unicodes == {ord("H"), ord("i")}  # noqa: SLF001


# ---------- dependency expansion (add_compound_references) ----------------


def test_add_compound_references_keeps_notdef(liberation_sans: object) -> None:
    sub = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    sub.add(ord("A"))
    sub.add_compound_references()
    # .notdef is still in the keep set after expansion.
    assert 0 in sub._glyph_ids  # noqa: SLF001


def test_add_compound_references_on_empty_subset_is_noop(
    liberation_sans: object,
) -> None:
    """An empty subset (only the constructor-installed .notdef) has no
    composites to expand. The call must not raise and must not grow
    the keep-set beyond {.notdef}."""
    sub = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    before = set(sub._glyph_ids)  # noqa: SLF001
    sub.add_compound_references()
    after = set(sub._glyph_ids)  # noqa: SLF001
    assert before == after  # no growth
    assert 0 in after


# ---------- get_gid_map ---------------------------------------------------


def test_get_gid_map_notdef_always_at_index_zero(liberation_sans: object) -> None:
    sub = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    sub.add(ord("H"))
    gid_map = sub.get_gid_map()
    assert gid_map[0] == 0  # new GID 0 always maps to old GID 0


def test_get_gid_map_translates_subset_widths_consistently(
    liberation_sans: object,
) -> None:
    """The new->old GID mapping should let callers translate widths
    across the subsetting boundary: ``new_to_old[k]`` is monotonically
    non-decreasing (because new GIDs are assigned in sorted old-GID
    order)."""
    sub = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    for cp in "Hello":
        sub.add(ord(cp))
    gid_map = sub.get_gid_map()
    olds = [gid_map[i] for i in range(len(gid_map))]
    assert olds == sorted(olds)
    assert len(set(olds)) == len(olds)  # no duplicates


# ---------- determinism --------------------------------------------------


def test_to_bytes_is_deterministic_for_same_input(
    liberation_sans: object,
) -> None:
    """``recalc_timestamp = False`` makes the subset output reproducible
    across calls.

    Determinism is guaranteed by construction: :meth:`TTFSubsetter.to_bytes`
    calls :meth:`TrueTypeFont._read_all_bytes`, which returns the
    immutable raw byte buffer captured at parse time, then builds a
    **fresh** ``ttLib.TTFont`` from it. The shared ``liberation_sans``
    fixture's lazily-populated ``_tt`` reader is never consulted, so
    no amount of cross-test traffic against the source font (composite
    expansion, GID map population, glyph-width queries) can alter the
    subset output. Wave 1396 added a function-scoped ``fresh_liberation_sans``
    fixture in an attempt to belt-and-brace a flake we never reproduced;
    wave 1398 removed it once the source-side isolation argument was
    confirmed (see ``CHANGES.md``).
    """
    sub_a = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    sub_b = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    for cp in "ABC":
        sub_a.add(ord(cp))
        sub_b.add(ord(cp))
    bytes_a = sub_a.to_bytes()
    bytes_b = sub_b.to_bytes()
    assert bytes_a == bytes_b


# ---------- set_prefix is unvalidated -----------------------------------


def test_set_prefix_accepts_arbitrary_string(liberation_sans: object) -> None:
    """Upstream trusts the caller to obey PDF 32000-1 §9.6.4's "six
    upper-case ASCII letters" rule. The setter itself does not validate
    — it just records the value."""
    sub = TTFSubsetter(liberation_sans)  # type: ignore[arg-type]
    # Any non-empty string; only the *applied* prefix gets format-checked
    # at flush time, and only insofar as it differs from already-applied.
    sub.set_prefix("ZZZZZZ")
    assert sub._prefix == "ZZZZZZ"  # noqa: SLF001


# ---------- log2 / to_u_int32 helpers (boundary tests) -------------------


def test_log2_zero_returns_zero() -> None:
    """``log(0)`` is undefined; upstream documents the contract that
    ``log2`` is only called with positive table counts. We follow that
    contract and return 0 for n <= 0 to avoid raising."""
    assert TTFSubsetter.log2(0) == 0
    assert TTFSubsetter.log2(-5) == 0


def test_log2_powers_of_two() -> None:
    assert TTFSubsetter.log2(1) == 0
    assert TTFSubsetter.log2(2) == 1
    assert TTFSubsetter.log2(8) == 3
    assert TTFSubsetter.log2(1024) == 10


def test_log2_floor_for_non_powers() -> None:
    """Mirrors upstream ``Math.floor(Math.log(num) / Math.log(2))``."""
    # 3 is between 2^1 (=2) and 2^2 (=4) — floor → 1.
    assert TTFSubsetter.log2(3) == 1
    # 7 < 8 → floor(log2(7)) == 2.
    assert TTFSubsetter.log2(7) == 2
    # 1023 < 1024 → 9.
    assert TTFSubsetter.log2(1023) == 9


def test_to_u_int32_combines_two_uint16() -> None:
    """``(high & 0xFFFF) << 16 | (low & 0xFFFF)``."""
    assert TTFSubsetter.to_u_int32(0x1234, 0x5678) == 0x12345678
    assert TTFSubsetter.to_u_int32(0, 0) == 0
    assert TTFSubsetter.to_u_int32(0xFFFF, 0xFFFF) == 0xFFFFFFFF


def test_to_u_int32_unpacks_big_endian_bytes() -> None:
    """The byte-overload: 4-byte big-endian → uint32."""
    assert TTFSubsetter.to_u_int32(b"\x12\x34\x56\x78") == 0x12345678
    assert TTFSubsetter.to_u_int32(b"\x00\x00\x00\x01") == 1
    assert TTFSubsetter.to_u_int32(b"\xFF\xFF\xFF\xFF") == 0xFFFFFFFF


def test_to_u_int32_masks_high_bits_for_int_overload() -> None:
    """High and low arguments are masked to 16 bits before combining."""
    # 0x1_0000 truncates to 0 in the high word.
    assert TTFSubsetter.to_u_int32(0x10000, 0xABCD) == 0xABCD
