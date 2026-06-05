"""Wave 1487 — ``PDResources.get_font`` always returns a typed ``PDFont``.

Upstream ``org.apache.pdfbox.pdmodel.PDResources.getFont(COSName)`` wraps
every font entry — direct (inline) and indirect alike — via
``PDFontFactory.createFont`` and returns a typed ``PDFont``; the document
resource cache is keyed by the indirect ``COSObject`` only, so direct entries
are wrapped fresh on each lookup and never cached.

pypdfbox previously preserved a legacy "raw ``COSDictionary`` for direct
entries" surface (cluster #1). This wave aligns it to upstream.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.pdmodel import PDDocument, PDResources
from pypdfbox.pdmodel.font import PDFont, PDType1Font

_FONT = COSName.get_pdf_name("Font")


def _type1_dict(base_font: str = "Helvetica") -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    d.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    d.set_name(COSName.BASE_FONT, base_font)  # type: ignore[attr-defined]
    return d


def test_direct_entry_returns_typed_pd_font() -> None:
    res = PDResources()
    font_dict = _type1_dict()
    res.put(_FONT, COSName.get_pdf_name("F0"), font_dict)

    font = res.get_font(COSName.get_pdf_name("F0"))

    assert isinstance(font, PDType1Font)
    assert font.get_cos_object() is font_dict


def test_direct_entry_not_cached_wrapped_fresh_each_lookup() -> None:
    # Upstream caches by indirect COSObject only; a direct (inline) dict is
    # wrapped fresh on each call, so identity is NOT preserved.
    doc = PDDocument()
    try:
        res = PDResources(document=doc)
        res.put(_FONT, COSName.get_pdf_name("F0"), _type1_dict())

        first = res.get_font(COSName.get_pdf_name("F0"))
        second = res.get_font(COSName.get_pdf_name("F0"))

        assert isinstance(first, PDFont)
        assert isinstance(second, PDFont)
        assert first is not second
    finally:
        doc.close()


def test_indirect_entry_returns_typed_pd_font_and_caches_identity() -> None:
    doc = PDDocument()
    try:
        res = PDResources(document=doc)
        name = COSName.get_pdf_name("F1")
        res.put(_FONT, name, COSObject(42, 0, resolved=_type1_dict()))

        first = res.get_font(name)
        second = res.get_font(name)

        assert isinstance(first, PDType1Font)
        assert first is second
    finally:
        doc.close()


def test_indirect_entry_without_cache_still_typed() -> None:
    # No document / resource cache attached: still returns a typed PDFont
    # (just no cross-call identity guarantee).
    res = PDResources()
    name = COSName.get_pdf_name("F1")
    res.put(_FONT, name, COSObject(7, 0, resolved=_type1_dict()))

    font = res.get_font(name)

    assert isinstance(font, PDType1Font)


def test_missing_entry_returns_none() -> None:
    res = PDResources()
    assert res.get_font(COSName.get_pdf_name("Nope")) is None


def test_non_dictionary_entry_returns_none() -> None:
    # A /Font value that is not a dictionary (malformed) resolves to None,
    # mirroring upstream's "base instanceof COSDictionary" guard.
    res = PDResources()
    res.put(_FONT, COSName.get_pdf_name("Bad"), COSInteger.get(3))
    assert res.get_font(COSName.get_pdf_name("Bad")) is None


def test_indirect_to_non_dictionary_returns_none() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("Bad2")
    res.put(_FONT, name, COSObject(9, 0, resolved=COSInteger.get(5)))
    assert res.get_font(name) is None
