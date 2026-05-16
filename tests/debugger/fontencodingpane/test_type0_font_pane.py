"""Focused tests for the three public ``Type0Font`` helpers ported in
wave 1311: ``get_encoding_name``, ``read_cid_to_gid_map`` and
``read_map``.

Each test calls the public method directly with a tiny hand-built stub
font, so they don't depend on Tk / Tcl being available at import time.
The full constructor path (which does need Tk) is already covered in
``test_type0_font.py``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.debugger.fontencodingpane.type0_font import Type0Font
from pypdfbox.pdmodel.font import PDType0Font


# ---- get_encoding_name -----------------------------------------------------


def _build_pdtype0_font(encoding: str | None) -> PDType0Font:
    """Build the smallest valid Type0 wrapper around a CIDFontType2
    descendant. When ``encoding`` is ``None`` no ``/Encoding`` key is set,
    which exercises the fallback branch in ``get_encoding_name``.
    """
    descendant = COSDictionary()
    descendant.set_name(COSName.get_pdf_name("Type"), "Font")
    descendant.set_name(COSName.get_pdf_name("Subtype"), "CIDFontType2")
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    sysinfo = COSDictionary()
    sysinfo.set_string(COSName.get_pdf_name("Registry"), "Adobe")
    sysinfo.set_string(COSName.get_pdf_name("Ordering"), "Identity")
    sysinfo.set_int(COSName.get_pdf_name("Supplement"), 0)
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), sysinfo)

    parent = COSDictionary()
    parent.set_name(COSName.get_pdf_name("Type"), "Font")
    parent.set_name(COSName.get_pdf_name("Subtype"), "Type0")
    parent.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    if encoding is not None:
        parent.set_item(
            COSName.get_pdf_name("Encoding"), COSName.get_pdf_name(encoding)
        )
    arr = COSArray()
    arr.add(descendant)
    parent.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    return PDType0Font(parent)


def test_get_encoding_name_identity_h() -> None:
    """When ``/Encoding`` is ``/Identity-H`` the label should match
    exactly (PDFBox upstream parity)."""
    font = _build_pdtype0_font("Identity-H")
    assert Type0Font.get_encoding_name(font) == "Identity-H"


def test_get_encoding_name_unicns_utf16_h() -> None:
    """Non-Identity CMap names round-trip too."""
    font = _build_pdtype0_font("UniCNS-UTF16-H")
    assert Type0Font.get_encoding_name(font) == "UniCNS-UTF16-H"


def test_get_encoding_name_missing_falls_back_to_class() -> None:
    """When ``/Encoding`` is absent the helper falls back to the
    cos-dict simple type name — mirrors upstream's
    ``getClass().getSimpleName()``."""
    font = _build_pdtype0_font(None)
    assert Type0Font.get_encoding_name(font) == "COSDictionary"


def test_get_encoding_name_alias_matches_public() -> None:
    """The legacy ``_get_encoding_name`` alias must point at the public
    promoted method (back-compat for any in-tree callers)."""
    assert Type0Font._get_encoding_name is Type0Font.get_encoding_name


# ---- read_cid_to_gid_map ---------------------------------------------------


class _StubCIDFontWithMap:
    """Smallest stub descendant exposing a ``/CIDToGIDMap`` stream — the
    constructor isn't invoked, so no Tk root is needed."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def get_path(self, _code: int) -> list[tuple[str, int, int]]:
        return []

    def get_cos_object(self) -> COSDictionary:
        stream = COSStream()
        stream.set_data(self._payload)
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("CIDToGIDMap"), stream)
        return d


class _StubParentNoUnicode:
    def to_unicode(self, _code: int) -> str | None:
        return None


def test_read_cid_to_gid_map_decodes_big_endian_pairs() -> None:
    """``read_cid_to_gid_map`` walks the byte stream as big-endian
    16-bit GIDs indexed by CID. Build a 4-entry table with mixed GID
    values, including zero (which suppresses the to_unicode call)."""
    # CID 0 -> GID 0x0000
    # CID 1 -> GID 0x0001
    # CID 2 -> GID 0x00FF
    # CID 3 -> GID 0x1234
    payload = b"\x00\x00\x00\x01\x00\xff\x12\x34"
    descendant = _StubCIDFontWithMap(payload)
    parent = _StubParentNoUnicode()
    # ``read_cid_to_gid_map`` is bound but doesn't actually need any
    # instance state besides the totals counter — construct a bare
    # instance via ``__new__`` to skip the constructor's Tk path.
    pane = Type0Font.__new__(Type0Font)
    pane._total_available_glyphs = 0
    rows = pane.read_cid_to_gid_map(descendant, parent)  # type: ignore[arg-type]
    assert rows is not None
    # 8 bytes / 2 = 4 rows.
    assert len(rows) == 4
    # Each row is [CID, GID, unicode_char, path].
    gids = {row[0]: row[1] for row in rows}
    assert gids == {0: 0x0000, 1: 0x0001, 2: 0x00FF, 3: 0x1234}


def test_read_cid_to_gid_map_returns_none_when_entry_missing() -> None:
    """When the descendant CIDFont has no ``/CIDToGIDMap`` entry the
    helper returns ``None`` (forcing the readMap fallback at the call
    site)."""

    class _NoMap:
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

        def get_path(self, _code: int) -> list[tuple[str, int, int]]:
            return []

    pane = Type0Font.__new__(Type0Font)
    pane._total_available_glyphs = 0
    assert (
        pane.read_cid_to_gid_map(_NoMap(), _StubParentNoUnicode())  # type: ignore[arg-type]
        is None
    )


def test_read_cid_to_gid_map_alias_matches_public() -> None:
    assert Type0Font._read_cid_to_gid_map is Type0Font.read_cid_to_gid_map


# ---- read_map --------------------------------------------------------------


class _SmallGlyphCIDFont:
    """Descendant stub that claims exactly three glyphs."""

    def __init__(self, glyph_codes: set[int]) -> None:
        self._glyph_codes = glyph_codes

    def has_glyph(self, code: int) -> bool:
        return code in self._glyph_codes

    def code_to_cid(self, code: int) -> int:
        return code

    def code_to_gid(self, code: int) -> int:
        return code + 100

    def get_path(self, _code: int) -> list[tuple[str, int, int]]:
        return []


class _SmallParentFont:
    def to_unicode(self, code: int) -> str | None:
        return chr(code) if 32 <= code <= 126 else None


def test_read_map_returns_one_row_per_glyph_code() -> None:
    """``read_map`` produces one row per code that ``has_glyph`` accepts.
    With a 3-glyph descendant we expect exactly 3 rows."""
    descendant = _SmallGlyphCIDFont(glyph_codes={65, 66, 67})  # A B C
    parent = _SmallParentFont()
    pane = Type0Font.__new__(Type0Font)
    pane._total_available_glyphs = 0
    rows = pane.read_map(descendant, parent)  # type: ignore[arg-type]
    assert len(rows) == 3
    # Each row: [code, cid, gid, unicode_char, path].
    codes = [row[0] for row in rows]
    assert codes == [65, 66, 67]
    gids = [row[2] for row in rows]
    assert gids == [165, 166, 167]
    unicode_chars = [row[3] for row in rows]
    assert unicode_chars == ["A", "B", "C"]


def test_read_map_empty_when_no_glyphs() -> None:
    descendant = _SmallGlyphCIDFont(glyph_codes=set())
    parent = _SmallParentFont()
    pane = Type0Font.__new__(Type0Font)
    pane._total_available_glyphs = 0
    rows = pane.read_map(descendant, parent)  # type: ignore[arg-type]
    assert rows == []


def test_read_map_alias_matches_public() -> None:
    assert Type0Font._read_map is Type0Font.read_map
