"""Coverage round-out for :class:`PDCIDFontType0` — wave 1339.

Targets the few remaining uncovered branches in
``pypdfbox/pdmodel/font/pd_cid_font_type0.py``:

* ``_uni_name_of_code_point`` short / wide hex paths (lines 42-45).
* ``get_glyph_name`` parent-resolved + empty-result paths (lines 589-592).
* ``get_path`` CIDToGIDMap remapping (lines 613-615) and the
  ``cs.get_path()`` exception swallow (lines 623-625).
* ``has_glyph`` ``cs is None`` early return (line 652) and ``get_gid``
  exception swallow (lines 655-656).
"""

from __future__ import annotations

import io
import struct

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_cid_font_type0 import (
    PDCIDFontType0,
    _uni_name_of_code_point,
)
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

# ----------------------------------------------------------------------
# CFF fixture (same shape as test_pd_cid_font_type0.py)
# ----------------------------------------------------------------------


def _build_cid_keyed_cff_bytes() -> bytes:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    glyph_order = [".notdef", "cid00001", "cid00002"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({1: glyph_order[1], 2: glyph_order[2]})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    cs_dict = {
        glyph_order[0]: _cs([0, "endchar"]),
        glyph_order[1]: _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto", "endchar"]
        ),
        glyph_order[2]: _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="TestCIDFontType0C",
        fontInfo={"FullName": "Test"},
        charStringsDict=cs_dict,
        privateDict={},
    )
    fb.setupHorizontalMetrics(
        {glyph_order[0]: (0, 0), glyph_order[1]: (500, 0), glyph_order[2]: (300, 0)}
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    re_open = TTFont(io.BytesIO(buf.getvalue()))
    return bytes(re_open.getTableData("CFF "))


def _make_font_with_embedded_cff() -> PDCIDFontType0:
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(_build_cid_keyed_cff_bytes())
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")
    descriptor.set_font_file3(stream)

    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbedded")
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return PDCIDFontType0(font_dict)


# ----------------------------------------------------------------------
# _uni_name_of_code_point (lines 42-45)
# ----------------------------------------------------------------------


def test_uni_name_of_code_point_pads_short_hex() -> None:
    """Codepoints below 0x1000 must be padded to 4 hex digits."""
    assert _uni_name_of_code_point(0x41) == "uni0041"
    assert _uni_name_of_code_point(0x100) == "uni0100"


def test_uni_name_of_code_point_keeps_wide_hex() -> None:
    """Codepoints above 0xFFFF render with their natural width."""
    assert _uni_name_of_code_point(0x1F600) == "uni1F600"


def test_uni_name_of_code_point_uppercases_hex() -> None:
    """The synthesised name uses uppercase hex (per UniUtil)."""
    assert _uni_name_of_code_point(0xABCD) == "uniABCD"


# ----------------------------------------------------------------------
# get_glyph_name parent-resolved paths (lines 589-592)
# ----------------------------------------------------------------------


class _StubParent:
    """A bare-bones :class:`PDType0Font` stand-in with a configurable
    ``to_unicode`` map.
    """

    def __init__(self, mapping: dict[int, str]) -> None:
        self._mapping = mapping

    def to_unicode(self, code: int) -> str | None:
        return self._mapping.get(code)


def test_get_glyph_name_returns_notdef_when_to_unicode_empty() -> None:
    """Parent's ``to_unicode`` returns an empty string -> ``.notdef``
    (covers lines 589-591)."""
    font = PDCIDFontType0()
    font._parent = _StubParent({0x41: ""})  # type: ignore[assignment]  # noqa: SLF001
    assert font.get_glyph_name(0x41) == ".notdef"


def test_get_glyph_name_returns_notdef_when_to_unicode_none() -> None:
    font = PDCIDFontType0()
    font._parent = _StubParent({})  # type: ignore[assignment]  # noqa: SLF001
    assert font.get_glyph_name(0x41) == ".notdef"


def test_get_glyph_name_returns_synthesised_uni_when_to_unicode_resolves() -> None:
    """Happy path: parent maps code -> ``A``; we emit ``uni0041``
    (covers line 592)."""
    font = PDCIDFontType0()
    font._parent = _StubParent({0x41: "A"})  # type: ignore[assignment]  # noqa: SLF001
    assert font.get_glyph_name(0x41) == "uni0041"


# ----------------------------------------------------------------------
# get_path CIDToGIDMap remap (lines 613-615)
# ----------------------------------------------------------------------


def _attach_cid_to_gid_map(font: PDCIDFontType0, mapping: list[int]) -> None:
    """Attach a /CIDToGIDMap stream that remaps CID -> GID per ``mapping``."""
    # Stream body: pairs of big-endian uint16s indexed by CID.
    body = b"".join(struct.pack(">H", g) for g in mapping)
    cid_to_gid_stream = COSStream()
    cid_to_gid_stream.set_data(body)
    font.get_cos_object().set_item(
        COSName.get_pdf_name("CIDToGIDMap"), cid_to_gid_stream
    )


def test_get_path_remaps_cid_via_cid_to_gid_map_stream() -> None:
    """An embedded CFF + a /CIDToGIDMap stream -> remap CID before
    charstring lookup (covers lines 613-615)."""
    font = _make_font_with_embedded_cff()
    # Map every CID to GID 0 — so even our known CID 1 ends up at notdef.
    _attach_cid_to_gid_map(font, [0, 0, 0])
    assert font.get_path(1) == []


# ----------------------------------------------------------------------
# get_path swallow on charstring exception (lines 623-625)
# ----------------------------------------------------------------------


class _RaisingCharString:
    """A charstring stand-in whose ``get_path`` raises an unexpected error."""

    def get_path(self) -> list:
        raise RuntimeError("simulated")

    def get_gid(self) -> int:
        return 1


def test_get_path_swallows_charstring_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """``cs.get_path()`` raises -> return ``[]`` (covers lines 623-624)."""
    font = _make_font_with_embedded_cff()
    monkeypatch.setattr(
        font, "get_type2_char_string", lambda _cid: _RaisingCharString()
    )
    assert font.get_path(1) == []


def test_get_path_returns_empty_when_program_present_but_charstring_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Program is present but the charstring lookup returns None ->
    trailing ``return []`` (covers line 625)."""
    font = _make_font_with_embedded_cff()
    monkeypatch.setattr(font, "get_type2_char_string", lambda _cid: None)
    assert font.get_path(1) == []


# ----------------------------------------------------------------------
# has_glyph: cs is None / get_gid raises (lines 652, 655-656)
# ----------------------------------------------------------------------


def test_has_glyph_returns_false_when_charstring_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``get_type2_char_string`` returns None -> False (line 652)."""
    font = _make_font_with_embedded_cff()
    monkeypatch.setattr(font, "get_type2_char_string", lambda _cid: None)
    assert font.has_glyph(1) is False


def test_has_glyph_returns_false_when_get_gid_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``cs.get_gid()`` raises -> False (covers lines 655-656)."""

    class _GidRaising:
        def get_gid(self) -> int:
            raise RuntimeError("simulated")

    font = _make_font_with_embedded_cff()
    monkeypatch.setattr(
        font, "get_type2_char_string", lambda _cid: _GidRaising()
    )
    assert font.has_glyph(1) is False
