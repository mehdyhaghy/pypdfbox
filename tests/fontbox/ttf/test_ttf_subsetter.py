"""Hand-written tests for :class:`pypdfbox.fontbox.ttf.TTFSubsetter`.

Loads the bundled LiberationSans-Regular fixture, asks the subsetter to
keep just the glyphs needed for "Hello", and verifies that the resulting
font is markedly smaller and that its cmap maps only the requested
codepoints. The subsetter wraps ``fontTools.subset`` — these tests treat
that as a black-box, asserting the upstream-compatible behaviour rather
than peeking at internal table layout.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_bytes() -> bytes:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return FIXTURE.read_bytes()


@pytest.fixture
def liberation_sans(liberation_bytes: bytes) -> TrueTypeFont:
    return TrueTypeFont.from_bytes(liberation_bytes)


def _load_fonttools(buf: bytes):
    import fontTools.ttLib as ttLib  # noqa: PLC0415

    return ttLib.TTFont(io.BytesIO(buf))


# ---------- basic shape ---------------------------------------------------


def test_constructor_accepts_truetypefont(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    assert sub is not None


def test_constructor_accepts_table_keep_list(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans, ["head", "hhea", "loca", "maxp", "glyf", "hmtx"])
    assert sub is not None


# ---------- subsetting "Hello" -------------------------------------------


def test_hello_subset_is_much_smaller(
    liberation_sans: TrueTypeFont, liberation_bytes: bytes
) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hello")
    out = sub.to_bytes()
    # Liberation Sans Regular is ~316 KiB; a 5-character subset must be a
    # small fraction of that. We pick a generous 1/3 ceiling so future
    # fontTools tweaks to default keep tables don't make this brittle.
    assert len(out) < len(liberation_bytes) // 3


def test_hello_subset_cmap_only_keeps_requested_codepoints(
    liberation_sans: TrueTypeFont,
) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hello")
    tt = _load_fonttools(sub.to_bytes())
    best = tt["cmap"].getBestCmap()
    # "Hello" → unique codepoints {H, e, l, o}.
    expected = {ord(c) for c in set("Hello")}
    assert set(best.keys()) == expected


def test_hello_subset_round_trips_via_truetypefont(
    liberation_sans: TrueTypeFont,
) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hello")
    sub_bytes = sub.to_bytes()
    # The subset must itself be parseable by our TrueTypeFont wrapper.
    sub_ttf = TrueTypeFont.from_bytes(sub_bytes)
    cmap = sub_ttf.get_unicode_cmap_subtable()
    assert cmap is not None
    assert cmap.get_glyph_id(ord("H")) != 0
    assert cmap.get_glyph_id(ord("e")) != 0
    # A character we did NOT register must map to .notdef in the subset.
    assert cmap.get_glyph_id(ord("Z")) == 0


# ---------- write_to_stream parity ---------------------------------------


def test_write_to_stream_matches_to_bytes(liberation_sans: TrueTypeFont) -> None:
    sub_a = TTFSubsetter(liberation_sans)
    sub_a.add_all(ord(c) for c in "abc")
    direct = sub_a.to_bytes()

    sub_b = TTFSubsetter(liberation_sans)
    sub_b.add_all(ord(c) for c in "abc")
    buf = io.BytesIO()
    sub_b.write_to_stream(buf)
    streamed = buf.getvalue()

    assert direct == streamed


# ---------- prefix tagging -----------------------------------------------


def test_set_prefix_tags_postscript_name(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hi")
    sub.set_prefix("ABCDEF")
    out = sub.to_bytes()
    tt = _load_fonttools(out)
    name_table = tt["name"]
    ps_record = name_table.getName(6, 3, 1, 0x409) or name_table.getName(6, 1, 0, 0)
    assert ps_record is not None
    assert ps_record.toUnicode().startswith("ABCDEF+")


def test_set_prefix_does_not_double_tag(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    sub.set_prefix("ABCDEF")
    first = TrueTypeFont.from_bytes(sub.to_bytes())

    # Re-subset the already-tagged output with the same prefix; the name
    # must stay singly-tagged (no "ABCDEF+ABCDEF+...").
    sub2 = TTFSubsetter(first)
    sub2.add(ord("A"))
    sub2.set_prefix("ABCDEF")
    out = sub2.to_bytes()
    tt = _load_fonttools(out)
    ps_name = tt["name"].getDebugName(6) or ""
    assert ps_name.count("ABCDEF+") == 1


# ---------- explicit GIDs -------------------------------------------------


def test_add_glyph_ids_keeps_requested_gids(liberation_sans: TrueTypeFont) -> None:
    # GID 1 in Liberation Sans is "space" (this is fixture-specific but
    # stable across Liberation 2.x). We don't depend on the *name*; we
    # only assert that the requested GID survives the round-trip.
    sub = TTFSubsetter(liberation_sans)
    sub.add_glyph_ids({1, 2, 3})
    tt = _load_fonttools(sub.to_bytes())
    # numGlyphs = .notdef + the three requested.
    assert tt["maxp"].numGlyphs >= 4


# ---------- empty subset (PDFBOX-2854) -----------------------------------


def test_empty_subset_keeps_only_notdef(liberation_sans: TrueTypeFont) -> None:
    """Mirror upstream's PDFBOX-2854 expectation: a subsetter with no
    ``add()`` calls still emits a valid TTF containing just ``.notdef``."""
    sub = TTFSubsetter(liberation_sans)
    out = sub.to_bytes()
    tt = _load_fonttools(out)
    assert tt["maxp"].numGlyphs == 1
    glyph_order = tt.getGlyphOrder()
    assert glyph_order[0] == ".notdef"
