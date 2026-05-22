"""Wave 198 — round-out hand-written tests for :class:`PDTrueTypeFont`.

Exercises the small remaining gaps relative to upstream:

* ``has_glyph(int code)`` / ``has_glyph(str name)`` polymorphic probe
* ``get_font_box_font`` (alias for :meth:`get_true_type_font`)
* ``read_code(stream)`` byte-stream reader
* ``get_path_by_name`` (handles the GID pseudo-name fallback)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_font_descriptor import FLAG_SYMBOLIC

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


def _font_with_embedded_ttf(
    liberation_bytes: bytes, *, symbolic: bool = False
) -> PDTrueTypeFont:
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    if symbolic:
        fd.set_flags(FLAG_SYMBOLIC)
    stream = COSStream()
    stream.set_raw_data(liberation_bytes)
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    font.set_true_type_font(TrueTypeFont.from_bytes(liberation_bytes))
    return font


# ---------- has_glyph(name) ---------------------------------------------


def test_has_glyph_by_name_true_for_known_glyph(liberation_bytes: bytes) -> None:
    """Liberation Sans carries a glyph for the canonical name 'A'."""
    font = _font_with_embedded_ttf(liberation_bytes)
    assert font.has_glyph("A") is True


def test_has_glyph_by_name_false_for_unknown_glyph(
    liberation_bytes: bytes,
) -> None:
    font = _font_with_embedded_ttf(liberation_bytes)
    assert font.has_glyph("definitely-not-a-real-glyph") is False


def test_has_glyph_by_name_false_without_program() -> None:
    """No embedded TTF — we can't probe the font program, so report False."""
    assert PDTrueTypeFont().has_glyph("A") is False


# ---------- has_glyph(code) ---------------------------------------------


def test_has_glyph_by_code_via_winansi(liberation_bytes: bytes) -> None:
    font = _font_with_embedded_ttf(liberation_bytes)
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    assert font.has_glyph(ord("A")) is True


def test_has_glyph_by_code_false_without_program() -> None:
    assert PDTrueTypeFont().has_glyph(65) is False


def test_has_glyph_by_code_symbolic_with_program(
    liberation_bytes: bytes,
) -> None:
    """Symbolic font + embedded TTF: the cmap is consulted directly."""
    font = _font_with_embedded_ttf(liberation_bytes, symbolic=True)
    assert font.has_glyph(ord("A")) is True


def test_has_glyph_rejects_bool() -> None:
    """``bool`` is technically an ``int`` subclass — guard against
    accidental ``has_glyph(True)`` calls (mirrors PDType3Font's check)."""
    font = PDTrueTypeFont()
    with pytest.raises(TypeError):
        font.has_glyph(True)  # type: ignore[arg-type]


# ---------- get_font_box_font ------------------------------------------


def test_get_font_box_font_returns_ttf(liberation_bytes: bytes) -> None:
    """``get_font_box_font`` is an alias for :meth:`get_true_type_font`
    (both return the embedded font program). Mirrors the upstream
    ``PDFontLike.getFontBoxFont`` accessor."""
    font = _font_with_embedded_ttf(liberation_bytes)
    fb_font = font.get_font_box_font()
    assert fb_font is not None
    assert fb_font is font.get_true_type_font()
    assert isinstance(fb_font, TrueTypeFont)


def test_get_font_box_font_none_when_not_embedded() -> None:
    assert PDTrueTypeFont().get_font_box_font() is None


# ---------- read_code ---------------------------------------------------


def test_read_code_reads_one_byte_from_bytes() -> None:
    """``read_code`` accepts raw bytes at an offset and returns
    ``(code, consumed)`` — TrueType simple fonts always consume 1 byte."""
    font = PDTrueTypeFont()
    assert font.read_code(b"X") == (ord("X"), 1)


def test_read_code_walks_offsets() -> None:
    font = PDTrueTypeFont()
    data = b"\x41\x42\x43"
    assert font.read_code(data, 0) == (0x41, 1)
    assert font.read_code(data, 1) == (0x42, 1)
    assert font.read_code(data, 2) == (0x43, 1)
    # Past end of buffer returns (0, 0) — caller terminates the loop.
    assert font.read_code(data, 3) == (0, 0)


def test_read_code_empty_buffer_returns_zero_zero() -> None:
    font = PDTrueTypeFont()
    assert font.read_code(b"") == (0, 0)


def test_read_code_accepts_bytearray_and_memoryview() -> None:
    font = PDTrueTypeFont()
    assert font.read_code(bytearray(b"Z")) == (ord("Z"), 1)
    assert font.read_code(memoryview(b"Y")) == (ord("Y"), 1)


# ---------- get_path_by_name -------------------------------------------


def test_get_path_by_name_resolves_known_glyph(
    liberation_bytes: bytes,
) -> None:
    font = _font_with_embedded_ttf(liberation_bytes)
    path = font.get_path_by_name("A")
    assert path, "expected at least one segment for glyph 'A'"
    assert path[0][0] == "moveTo"


def test_get_path_by_name_notdef_is_empty(liberation_bytes: bytes) -> None:
    """``.notdef`` paths are deliberately empty (mirrors PDFBOX-2421)."""
    font = _font_with_embedded_ttf(liberation_bytes)
    assert font.get_path_by_name(".notdef") == []


def test_get_path_by_name_gid_pseudo_name(liberation_bytes: bytes) -> None:
    """When a name doesn't map to a glyph but is a decimal integer, it's
    treated as a GID pseudo-name. Mirrors upstream's ``getPath(String)``
    fallback path used by encoded-glyph decoders."""
    font = _font_with_embedded_ttf(liberation_bytes)
    ttf = font.get_true_type_font()
    assert ttf is not None
    # Pick a known-good GID by resolving 'A' through the cmap.
    cmap = ttf.get_unicode_cmap_subtable()
    assert cmap is not None
    gid_a = cmap.get_glyph_id(ord("A"))
    assert gid_a > 0
    path_via_pseudo = font.get_path_by_name(str(gid_a))
    assert path_via_pseudo, "expected a path for GID pseudo-name"


def test_get_path_by_name_out_of_range_gid_is_empty(
    liberation_bytes: bytes,
) -> None:
    font = _font_with_embedded_ttf(liberation_bytes)
    ttf = font.get_true_type_font()
    assert ttf is not None
    too_big = ttf.get_number_of_glyphs() + 1000
    assert font.get_path_by_name(str(too_big)) == []


def test_get_path_by_name_no_program_empty() -> None:
    assert PDTrueTypeFont().get_path_by_name("A") == []


def test_get_path_by_name_empty_string_is_empty(
    liberation_bytes: bytes,
) -> None:
    font = _font_with_embedded_ttf(liberation_bytes)
    assert font.get_path_by_name("") == []
