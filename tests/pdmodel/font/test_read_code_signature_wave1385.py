"""Wave 1385 — uniform ``read_code(data, offset) -> (code, consumed)`` signature.

Wave 1384's audit found that :class:`PDType0Font.read_code` accepted the
renderer's ``(bytes, offset)`` call shape, while the simple-font ports
(:class:`PDTrueTypeFont`, :class:`PDType1Font`, :class:`PDType1CFont`,
:class:`PDType3Font`) still declared the legacy ``read_code(stream)`` form
returning a plain ``int``. The renderer's call at
``pdf_renderer.PDFRenderer._show_string`` does
``font.read_code(data, offset)`` and unpacks ``(code, consumed)`` — so
every simple-font glyph fetch raised :class:`TypeError`, fell back to a
raw ``data[offset]`` byte read and skipped the uniform decode contract.

Visible symptom (before wave 1385): glyph dispatch logged a debug message
per simple-font glyph and the renderer's word-spacing branch never saw a
proper ``consumed`` value.

This wave normalises the signature: **all five PDFont subclasses** now
accept ``(data, offset=0)`` and return ``(code, consumed)``. The simple
fonts always consume exactly 1 byte (single-byte character codes per
PDFBox' Java implementation); the composite ``PDType0Font`` defers to its
active CMap and may consume 1–4 bytes.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font import (
    PDTrueTypeFont,
    PDType0Font,
    PDType1CFont,
    PDType1Font,
    PDType3Font,
)

# ---------- simple fonts: (data, offset) -> (code, 1) ----------


SIMPLE_FONT_CLASSES = [PDTrueTypeFont, PDType1Font, PDType1CFont, PDType3Font]


@pytest.mark.parametrize(
    "font_cls",
    SIMPLE_FONT_CLASSES,
    ids=[cls.__name__ for cls in SIMPLE_FONT_CLASSES],
)
def test_simple_font_read_code_returns_tuple(font_cls: type) -> None:
    """Every simple font accepts ``(data, offset)`` and returns
    ``(code, consumed)`` — never a bare ``int``."""
    font = font_cls()
    result = font.read_code(b"\x41")
    assert isinstance(result, tuple)
    assert len(result) == 2
    code, consumed = result
    assert code == 0x41
    assert consumed == 1


@pytest.mark.parametrize(
    "font_cls",
    SIMPLE_FONT_CLASSES,
    ids=[cls.__name__ for cls in SIMPLE_FONT_CLASSES],
)
def test_simple_font_read_code_walks_offsets(font_cls: type) -> None:
    """Sequential ``read_code`` calls advance through the buffer one
    byte at a time and return the correct codes."""
    font = font_cls()
    data = b"\x41\x42\x43\xFF"
    offset = 0
    codes = []
    while offset < len(data):
        code, consumed = font.read_code(data, offset)
        if consumed <= 0:
            break
        codes.append(code)
        offset += consumed
    assert codes == [0x41, 0x42, 0x43, 0xFF]


@pytest.mark.parametrize(
    "font_cls",
    SIMPLE_FONT_CLASSES,
    ids=[cls.__name__ for cls in SIMPLE_FONT_CLASSES],
)
def test_simple_font_read_code_past_end_returns_zero_zero(
    font_cls: type,
) -> None:
    """At-or-past-end-of-buffer reads return ``(0, 0)`` so the renderer's
    decode loop terminates rather than spinning."""
    font = font_cls()
    assert font.read_code(b"") == (0, 0)
    assert font.read_code(b"\x00", 1) == (0, 0)
    assert font.read_code(b"\x00\x01", 5) == (0, 0)


@pytest.mark.parametrize(
    "font_cls",
    SIMPLE_FONT_CLASSES,
    ids=[cls.__name__ for cls in SIMPLE_FONT_CLASSES],
)
def test_simple_font_read_code_negative_offset_returns_zero_zero(
    font_cls: type,
) -> None:
    """Defensive: negative offsets must not raise; they terminate the
    decode loop the same way an at-end read does."""
    font = font_cls()
    assert font.read_code(b"\x41", -1) == (0, 0)


@pytest.mark.parametrize(
    "font_cls",
    SIMPLE_FONT_CLASSES,
    ids=[cls.__name__ for cls in SIMPLE_FONT_CLASSES],
)
def test_simple_font_read_code_accepts_bytearray_and_memoryview(
    font_cls: type,
) -> None:
    """``read_code`` accepts any bytes-like buffer (bytearray /
    memoryview) — caller convenience for content streams sliced from
    larger buffers."""
    font = font_cls()
    assert font.read_code(bytearray(b"\x7F")) == (0x7F, 1)
    assert font.read_code(memoryview(b"\x80")) == (0x80, 1)


# ---------- composite font: PDType0Font already has the right shape ----------


def test_type0_font_read_code_returns_tuple() -> None:
    """:class:`PDType0Font.read_code` has always had the
    ``(data, offset) -> (code, consumed)`` signature. Pin it here so any
    future refactor that drifts the shape gets caught by this wave's
    suite."""
    font = PDType0Font()
    result = font.read_code(b"\x41")
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_type0_font_read_code_past_end_returns_zero_zero() -> None:
    font = PDType0Font()
    assert font.read_code(b"", 0) == (0, 0)
    assert font.read_code(b"\x00", 5) == (0, 0)


# ---------- uniform contract: all 5 classes agree ----------


ALL_FONT_CLASSES = [*SIMPLE_FONT_CLASSES, PDType0Font]


@pytest.mark.parametrize(
    "font_cls",
    ALL_FONT_CLASSES,
    ids=[cls.__name__ for cls in ALL_FONT_CLASSES],
)
def test_read_code_signature_uniform_across_all_pdfont_subclasses(
    font_cls: type,
) -> None:
    """Single contract check: every PDFont subclass that overrides
    ``read_code`` accepts ``(data, offset)`` and returns ``(code,
    consumed)`` — the renderer's :meth:`_show_string` dispatch depends
    on this."""
    font = font_cls()
    # Call with positional (data, offset) — the renderer's call shape.
    result = font.read_code(b"\x41\x00", 0)
    assert isinstance(result, tuple)
    code, consumed = result
    assert isinstance(code, int)
    assert isinstance(consumed, int)
    assert consumed >= 0
