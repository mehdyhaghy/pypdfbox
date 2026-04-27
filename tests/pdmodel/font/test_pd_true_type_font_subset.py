"""Hand-written tests for :meth:`PDTrueTypeFont.subset`.

Covers the integration between :class:`PDTrueTypeFont` and
:class:`pypdfbox.fontbox.ttf.TTFSubsetter`: a fully-loaded TrueType font
embedded under ``/FontFile2`` is subset down to a handful of codepoints,
the descriptor's stream is replaced with the smaller subset bytes, and
the PostScript ``/BaseFont`` (plus mirrored ``/FontName``) gets the
six-letter PDF subset tag prepended.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont

_TTF_FIXTURE = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_bytes() -> bytes:
    if not _TTF_FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {_TTF_FIXTURE}")
    return _TTF_FIXTURE.read_bytes()


def _build_font(liberation_bytes: bytes) -> PDTrueTypeFont:
    """Construct a PDTrueTypeFont whose ``/FontFile2`` is the bundled
    Liberation Sans fixture, with /BaseFont and /FontName set."""
    font = PDTrueTypeFont()
    font.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "LiberationSans"
    )
    fd = PDFontDescriptor()
    fd.set_font_name("LiberationSans")
    stream = COSStream()
    stream.set_raw_data(liberation_bytes)
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    font.set_true_type_font(TrueTypeFont.from_bytes(liberation_bytes))
    return font


# ---------- subset returns valid bytes -----------------------------------


def test_subset_returns_subset_bytes_smaller_than_original(
    liberation_bytes: bytes,
) -> None:
    font = _build_font(liberation_bytes)
    out = font.subset("Hello World")
    # 11 unique characters (incl. space). Liberation Sans is ~316 KiB; a
    # subset must be a small fraction. Generous 1/3 ceiling matches the
    # TTFSubsetter unit-test expectation.
    assert len(out) < len(liberation_bytes) // 3
    assert isinstance(out, bytes)


def test_subset_replaces_font_file2_with_subset_bytes(
    liberation_bytes: bytes,
) -> None:
    font = _build_font(liberation_bytes)
    out = font.subset("Hello World")
    fd = font.get_font_descriptor()
    assert fd is not None
    new_stream = fd.get_font_file2()
    assert new_stream is not None
    # The descriptor's /FontFile2 now holds the subset bytes verbatim.
    assert new_stream.to_byte_array() == out


def test_subset_preserves_font_file2_stream_identity(
    liberation_bytes: bytes,
) -> None:
    """When a /FontFile2 stream already exists, subset() must mutate it
    in-place rather than installing a fresh COSStream — so any other
    reference (e.g. from indirect-object writeback) still points at the
    same instance."""
    font = _build_font(liberation_bytes)
    fd = font.get_font_descriptor()
    assert fd is not None
    before = fd.get_font_file2()
    assert before is not None
    before_cos = before.get_cos_object()

    font.subset("ABC")
    after = fd.get_font_file2()
    assert after is not None
    assert after.get_cos_object() is before_cos


# ---------- /BaseFont tag ------------------------------------------------


def test_subset_prefixes_base_font_with_six_letter_tag(
    liberation_bytes: bytes,
) -> None:
    font = _build_font(liberation_bytes)
    font.subset("Hello")
    name = font.get_name()
    assert name is not None
    # ABCDEF+LiberationSans → 7th char is '+', first 6 are uppercase.
    assert len(name) >= 7
    assert name[6] == "+"
    assert name[:6].isalpha()
    assert name[:6].isupper()
    assert name.endswith("LiberationSans")


def test_subset_marks_font_as_subset(liberation_bytes: bytes) -> None:
    font = _build_font(liberation_bytes)
    assert font.is_subset() is False
    font.subset("Hello")
    assert font.is_subset() is True


def test_subset_explicit_prefix_is_used(liberation_bytes: bytes) -> None:
    font = _build_font(liberation_bytes)
    font.subset("Hi", prefix="ABCDEF")
    assert font.get_name() == "ABCDEF+LiberationSans"


def test_subset_does_not_double_tag(liberation_bytes: bytes) -> None:
    font = _build_font(liberation_bytes)
    font.subset("Hi", prefix="ABCDEF")
    # Re-subset should not stack tags.
    font.subset("Hi", prefix="ZZZZZZ")
    name = font.get_name()
    assert name is not None
    # Exactly one '+' separator survives.
    assert name.count("+") == 1


# ---------- /FontName mirror ---------------------------------------------


def test_subset_mirrors_tag_onto_descriptor_font_name(
    liberation_bytes: bytes,
) -> None:
    font = _build_font(liberation_bytes)
    font.subset("Hello", prefix="ABCDEF")
    fd = font.get_font_descriptor()
    assert fd is not None
    assert fd.get_font_name() == "ABCDEF+LiberationSans"


# ---------- accumulated codepoints / used_chars --------------------------


def test_add_to_subset_accumulates_codepoints(liberation_bytes: bytes) -> None:
    font = _build_font(liberation_bytes)
    for ch in "Hi":
        font.add_to_subset(ord(ch))
    out = font.subset()
    # Subset must still be tiny (at most 2 visible glyphs + .notdef).
    assert len(out) < len(liberation_bytes) // 3


def test_used_chars_argument_supplements_text(liberation_bytes: bytes) -> None:
    font = _build_font(liberation_bytes)
    font.subset(used_chars=[ord("A"), ord("B"), ord("C")])
    fd = font.get_font_descriptor()
    assert fd is not None
    new_stream = fd.get_font_file2()
    assert new_stream is not None
    # Round-trip through TrueTypeFont and confirm the requested glyphs
    # all map to non-zero GIDs while a non-requested codepoint does not.
    sub = TrueTypeFont.from_bytes(new_stream.to_byte_array())
    cmap = sub.get_unicode_cmap_subtable()
    assert cmap is not None
    assert cmap.get_glyph_id(ord("A")) != 0
    assert cmap.get_glyph_id(ord("B")) != 0
    assert cmap.get_glyph_id(ord("Z")) == 0


def test_subset_clears_accumulated_codepoints(liberation_bytes: bytes) -> None:
    font = _build_font(liberation_bytes)
    font.add_to_subset(ord("A"))
    font.subset()
    assert font._subset_codepoints == set()  # noqa: SLF001


# ---------- error cases --------------------------------------------------


def test_subset_raises_when_no_font_program() -> None:
    font = PDTrueTypeFont()
    font.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "Bare"
    )
    with pytest.raises(ValueError, match="cannot subset"):
        font.subset("Hi")
