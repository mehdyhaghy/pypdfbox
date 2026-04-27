"""Hand-written tests for :meth:`PDType0Font.subset`.

A composite (Type 0) font wraps a descendant CIDFontType2 whose
``/FontFile2`` carries the actual TrueType program. ``subset()`` must
rewrite the descendant's ``/FontFile2`` and prepend the six-letter PDF
subset tag to both the parent ``/BaseFont`` and the descendant's
``/BaseFont`` / descriptor ``/FontName``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

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


def _build_type0(liberation_bytes: bytes) -> PDType0Font:
    """Construct a Type 0 font whose descendant CIDFontType2 carries
    the bundled Liberation Sans fixture as ``/FontFile2``."""
    descendant = PDCIDFontType2()
    descendant.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "LiberationSans"
    )
    fd = PDFontDescriptor()
    fd.set_font_name("LiberationSans")
    stream = COSStream()
    stream.set_raw_data(liberation_bytes)
    fd.set_font_file2(stream)
    descendant.set_font_descriptor(fd)
    descendant.set_true_type_font(TrueTypeFont.from_bytes(liberation_bytes))

    parent = PDType0Font()
    parent.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "LiberationSans"
    )
    arr = COSArray()
    arr.add(descendant.get_cos_object())
    parent.get_cos_object().set_item(
        COSName.get_pdf_name("DescendantFonts"), arr
    )
    parent.get_cos_object().set_name(
        COSName.get_pdf_name("Encoding"), "Identity-H"
    )
    return parent


# ---------- subset returns valid bytes -----------------------------------


def test_subset_returns_subset_bytes_smaller_than_original(
    liberation_bytes: bytes,
) -> None:
    parent = _build_type0(liberation_bytes)
    out = parent.subset("Hello World")
    assert len(out) < len(liberation_bytes) // 3
    assert isinstance(out, bytes)


def test_subset_replaces_descendant_font_file2(liberation_bytes: bytes) -> None:
    parent = _build_type0(liberation_bytes)
    out = parent.subset("Hello World")
    descendant = parent.get_descendant_font()
    assert descendant is not None
    fd = descendant.get_font_descriptor()
    assert fd is not None
    new_stream = fd.get_font_file2()
    assert new_stream is not None
    assert new_stream.to_byte_array() == out


# ---------- six-letter tag on /BaseFont (parent + descendant) ------------


def test_subset_tags_parent_and_descendant_base_font(
    liberation_bytes: bytes,
) -> None:
    parent = _build_type0(liberation_bytes)
    parent.subset("Hello", prefix="ABCDEF")
    assert parent.get_name() == "ABCDEF+LiberationSans"
    descendant = parent.get_descendant_font()
    assert descendant is not None
    assert descendant.get_name() == "ABCDEF+LiberationSans"


def test_subset_random_tag_when_no_prefix(liberation_bytes: bytes) -> None:
    parent = _build_type0(liberation_bytes)
    parent.subset("Hi")
    name = parent.get_name()
    assert name is not None
    assert len(name) >= 7
    assert name[6] == "+"
    assert name[:6].isalpha()
    assert name[:6].isupper()


def test_subset_marks_font_as_subset(liberation_bytes: bytes) -> None:
    parent = _build_type0(liberation_bytes)
    assert parent.is_subset() is False
    parent.subset("Hello")
    assert parent.is_subset() is True


def test_subset_does_not_double_tag(liberation_bytes: bytes) -> None:
    parent = _build_type0(liberation_bytes)
    parent.subset("Hi", prefix="ABCDEF")
    parent.subset("Hi", prefix="ZZZZZZ")
    name = parent.get_name()
    assert name is not None
    assert name.count("+") == 1


# ---------- descriptor /FontName mirror ----------------------------------


def test_subset_mirrors_tag_onto_descriptor_font_name(
    liberation_bytes: bytes,
) -> None:
    parent = _build_type0(liberation_bytes)
    parent.subset("Hello", prefix="ABCDEF")
    descendant = parent.get_descendant_font()
    assert descendant is not None
    fd = descendant.get_font_descriptor()
    assert fd is not None
    assert fd.get_font_name() == "ABCDEF+LiberationSans"


# ---------- accumulated codepoints / used_chars --------------------------


def test_add_to_subset_accumulates_codepoints(liberation_bytes: bytes) -> None:
    parent = _build_type0(liberation_bytes)
    parent.add_to_subset(ord("H"))
    parent.add_to_subset(ord("i"))
    out = parent.subset()
    assert len(out) < len(liberation_bytes) // 3


def test_used_chars_kwarg_keeps_glyphs(liberation_bytes: bytes) -> None:
    parent = _build_type0(liberation_bytes)
    parent.subset(used_chars=[ord("A"), ord("B"), ord("C")])
    descendant = parent.get_descendant_font()
    assert descendant is not None
    fd = descendant.get_font_descriptor()
    assert fd is not None
    new_stream = fd.get_font_file2()
    assert new_stream is not None
    sub = TrueTypeFont.from_bytes(new_stream.to_byte_array())
    cmap = sub.get_unicode_cmap_subtable()
    assert cmap is not None
    assert cmap.get_glyph_id(ord("A")) != 0
    assert cmap.get_glyph_id(ord("B")) != 0
    assert cmap.get_glyph_id(ord("Z")) == 0


def test_subset_clears_accumulated_codepoints(liberation_bytes: bytes) -> None:
    parent = _build_type0(liberation_bytes)
    parent.add_to_subset(ord("A"))
    parent.subset()
    assert parent._subset_codepoints == set()  # noqa: SLF001


# ---------- error cases --------------------------------------------------


def test_subset_raises_when_no_descendant_font() -> None:
    parent = PDType0Font()
    with pytest.raises(ValueError, match="no descendant"):
        parent.subset("Hi")


def test_subset_raises_when_descendant_has_no_font_file2() -> None:
    parent = PDType0Font()
    descendant = PDCIDFontType2()
    descendant.set_font_descriptor(PDFontDescriptor())
    arr = COSArray()
    arr.add(descendant.get_cos_object())
    parent.get_cos_object().set_item(
        COSName.get_pdf_name("DescendantFonts"), arr
    )
    with pytest.raises(ValueError, match="no embedded /FontFile2"):
        parent.subset("Hi")
