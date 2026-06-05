"""Wave 1490 — symbol-cmap / ToUnicode encode fallback for embedded Type0 fonts.

Covers the WRITE/encode side of ``PDType0Font`` for an embedded, Identity-H
symbolic subset CIDFontType2 whose embedded program carries no usable unicode
cmap (only a ``(3,0)`` Microsoft-symbol cmap, or no cmap at all).

Before this wave, ``PDType0Font.encode`` short-circuited to
``_encode_codepoint`` whenever ``PDCIDFontType2.get_cmap_lookup()`` returned
``None``, which (under Identity-H) emitted the *raw Unicode codepoint* as the
CID. That diverged from upstream ``PDCIDFontType2.encode``, which on a
cmap-lookup miss falls back to the parent ``/ToUnicode`` CMap's reverse lookup
(``getCodesFromUnicode``) to recover the real descendant code.

The canonical reproducer (eu-001.pdf's ``JMGKCC+Symbol``) is pinned by the live
oracle in ``oracle/test_type0_encode_width_oracle.py``: PDFBox encodes U+2022 to
CID 0x78 with advance 459, the pre-fix pypdfbox emitted 0x2022 / advance 1000.
These hand-written tests pin the model-layer contract directly with synthetic
fonts so the fix is covered without the oracle jar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument

_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
_EU001 = _FIXTURES / "text" / "input" / "eu-001.pdf"


# ---------- synthetic-font contract tests (no fixture needed) ----------


def _to_unicode_stream() -> COSStream:
    """A minimal /ToUnicode CMap that reverse-maps U+2022 (bullet) to the
    descendant byte sequence 0x0078 (CID 0x78), mirroring eu-001's font.
    """
    text = (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\n"
        "begincmap\n"
        "1 begincodespacerange\n"
        "<0000> <FFFF>\n"
        "endcodespacerange\n"
        "1 beginbfchar\n"
        "<0078> <2022>\n"
        "endbfchar\n"
        "endcmap\n"
        "CMapName currentdict /CMap defineresource pop\n"
        "end\nend\n"
    )
    stream = COSStream()
    stream.set_data(text.encode("ascii"))
    return stream


def _build_symbolic_type0() -> PDType0Font:
    """Build an Identity-H Type0 font whose descendant reports embedded but has
    no usable unicode cmap lookup, with a /ToUnicode that reverse-maps U+2022 ->
    0x0078. This reproduces the eu-001 shape without an embedded program.
    """
    cid_dict = COSDictionary()
    cid_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    cid_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("CIDFontType2")
    )
    # /W: CID 0x78 has width 459 (the eu-001 value).
    w = COSArray()
    w.add(COSInteger.get(0x78))
    inner = COSArray()
    inner.add(COSInteger.get(459))
    w.add(inner)
    cid_dict.set_item(COSName.get_pdf_name("W"), w)

    descendant = PDCIDFontType2(cid_dict)

    type0_dict = COSDictionary()
    type0_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    type0_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type0")
    )
    type0_dict.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("Identity-H")
    )
    desc_array = COSArray()
    desc_array.add(cid_dict)
    type0_dict.set_item(COSName.get_pdf_name("DescendantFonts"), desc_array)
    type0_dict.set_item(COSName.get_pdf_name("ToUnicode"), _to_unicode_stream())

    font = PDType0Font(type0_dict)
    # Pin a single descendant instance (get_descendant_font re-wraps on each
    # call) and stub the embedded/cmap probes to mirror a no-cmap embedded
    # program — the eu-001 shape without an actual /FontFile2.
    descendant.is_embedded = lambda: True  # type: ignore[method-assign]
    descendant.get_cmap_lookup = lambda: None  # type: ignore[method-assign]
    font.get_descendant_font = lambda: descendant  # type: ignore[method-assign]
    return font


def test_symbolic_encode_uses_to_unicode_fallback() -> None:
    """An embedded Identity-H font with no unicode cmap encodes U+2022 through
    the parent /ToUnicode reverse lookup, yielding the real CID 0x78 — NOT the
    raw codepoint 0x2022.
    """
    font = _build_symbolic_type0()
    assert font.encode(chr(0x2022)) == b"\x00\x78"


def test_symbolic_string_width_uses_to_unicode_fallback() -> None:
    """get_string_width sums the real descendant /W advance (459) after the
    ToUnicode-recovered CID, not the /DW / notdef default for the raw codepoint.
    """
    font = _build_symbolic_type0()
    assert font.get_string_width(chr(0x2022)) == 459.0


def test_symbolic_encode_unencodable_keeps_lenient_notdef() -> None:
    """A codepoint absent from BOTH the embedded cmap and /ToUnicode keeps the
    documented lenient .notdef (CID 0) substitution — encode must NOT raise and
    must NOT emit the raw codepoint.
    """
    font = _build_symbolic_type0()
    # U+0041 ('A') is not in the synthetic /ToUnicode reverse map.
    out = font.encode("A")
    assert out == b"\x00\x00"  # CID 0 (.notdef), lenient fallback


def test_embedded_identity_with_cmap_lookup_still_used() -> None:
    """When the embedded program DOES carry a unicode cmap lookup, encode uses
    it (codepoint -> GID) ahead of the /ToUnicode fallback — the cmap result
    wins.
    """
    font = _build_symbolic_type0()

    class _Lookup:
        def get_glyph_id(self, cp: int) -> int:
            return 0x99 if cp == 0x2022 else 0

    font.get_descendant_font().get_cmap_lookup = lambda: _Lookup()  # type: ignore[method-assign]
    # cmap lookup resolves 0x2022 -> 0x99, taking priority over ToUnicode 0x78.
    assert font.encode(chr(0x2022)) == b"\x00\x99"


# ---------- real-fixture regression (eu-001 reproducer) ----------


def _eu001_symbol_font() -> PDType0Font | None:
    doc = PDDocument.load(_EU001)
    try:
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                if isinstance(font, PDType0Font) and "Symbol" in (
                    font.get_name() or ""
                ):
                    # Read everything we need before closing the document.
                    enc = font.encode(chr(0x2022))
                    sw = font.get_string_width(chr(0x2022))
                    return enc, sw  # type: ignore[return-value]
    finally:
        doc.close()
    return None


@pytest.mark.skipif(not _EU001.is_file(), reason="eu-001.pdf fixture missing")
def test_eu001_symbol_bullet_encode_and_width() -> None:
    """End-to-end on the real reproducer: the JMGKCC+Symbol font (embedded
    /FontFile2 with NO cmap table) encodes U+2022 to CID 0x78 with advance 459
    via the /ToUnicode reverse lookup — matching PDFBox (pre-fix: 0x2022 / 1000).
    """
    result = _eu001_symbol_font()
    assert result is not None, "no Symbol Type0 font found in eu-001.pdf"
    enc, sw = result
    assert enc == b"\x00\x78"
    assert sw == 459.0
