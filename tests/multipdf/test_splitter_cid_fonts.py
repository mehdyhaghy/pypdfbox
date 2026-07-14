"""Hand-written tests for :class:`pypdfbox.multipdf.Splitter`'s handling
of CID font subsets. Embedded CID font subset programs (``/FontFile2``,
``/FontFile3``) live inside the page's ``/Resources /Font`` chain — the
splitter's deep-copy must carry these stream bodies into each chunk
verbatim. Truncating or losing the subset program corrupts the font and
breaks downstream rendering.
"""
from __future__ import annotations

import io

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.multipdf import Splitter

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_BASEFONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")
_DESCENDANT_FONTS = COSName.get_pdf_name("DescendantFonts")
_FONT_DESCRIPTOR = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE2 = COSName.get_pdf_name("FontFile2")
_FONT_FILE3 = COSName.get_pdf_name("FontFile3")
_FONT = COSName.get_pdf_name("Font")
_RESOURCES = COSName.get_pdf_name("Resources")
_LENGTH1 = COSName.get_pdf_name("Length1")
_CIDSYSTEMINFO = COSName.get_pdf_name("CIDSystemInfo")


def _attach_f1_content(page: PDPage) -> None:
    """Give ``page`` a content stream that uses ``/F1`` — the splitter
    prunes resource entries its content never references, so a page whose
    font should survive the split must actually select it."""
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(b"BT /F1 12 Tf (x) Tj ET")
    page.set_contents(stream)


# Synthetic TTF subset payload — non-trivial bytes to verify no
# truncation. Real TrueType subsets start with `\x00\x01\x00\x00` (sfnt
# version) but the splitter doesn't introspect contents, so any
# byte-pattern works for round-trip purposes.
_SUBSET_BYTES = b"\x00\x01\x00\x00" + bytes(range(256)) * 4


def _make_cid_font_resources() -> COSDictionary:
    """Build a minimal /Type0 + CIDFontType2 + FontDescriptor + /FontFile2
    chain that mirrors the real-world embedded-CID-subset shape.
    """
    # /FontFile2 stream — the actual subset program.
    font_file2 = COSStream()
    font_file2.set_item(_LENGTH1, COSInteger.get(len(_SUBSET_BYTES)))
    # set_data writes (and re-encodes) — we want raw bytes preserved.
    font_file2.create_raw_output_stream().write(_SUBSET_BYTES)

    # /FontDescriptor.
    descriptor = COSDictionary()
    descriptor.set_item(_TYPE, COSName.get_pdf_name("FontDescriptor"))
    descriptor.set_item(COSName.get_pdf_name("FontName"),
                        COSName.get_pdf_name("ABCDEF+NotoSans"))
    descriptor.set_item(_FONT_FILE2, font_file2)

    # /CIDFontType2 descendant.
    cid_system_info = COSDictionary()
    cid_system_info.set_item(COSName.get_pdf_name("Registry"),
                             COSName.get_pdf_name("Adobe"))
    cid_system_info.set_item(COSName.get_pdf_name("Ordering"),
                             COSName.get_pdf_name("Identity"))
    cid_system_info.set_item(COSName.get_pdf_name("Supplement"),
                             COSInteger.get(0))

    cid_font = COSDictionary()
    cid_font.set_item(_TYPE, _FONT)
    cid_font.set_item(_SUBTYPE, COSName.get_pdf_name("CIDFontType2"))
    cid_font.set_item(_BASEFONT, COSName.get_pdf_name("ABCDEF+NotoSans"))
    cid_font.set_item(_FONT_DESCRIPTOR, descriptor)
    cid_font.set_item(_CIDSYSTEMINFO, cid_system_info)

    # /Type0 wrapper.
    descendants = COSArray()
    descendants.add(cid_font)

    type0 = COSDictionary()
    type0.set_item(_TYPE, _FONT)
    type0.set_item(_SUBTYPE, COSName.get_pdf_name("Type0"))
    type0.set_item(_BASEFONT, COSName.get_pdf_name("ABCDEF+NotoSans"))
    type0.set_item(_ENCODING, COSName.get_pdf_name("Identity-H"))
    type0.set_item(_DESCENDANT_FONTS, descendants)

    # /Resources /Font /F1 → /Type0.
    fonts = COSDictionary()
    fonts.set_item(COSName.get_pdf_name("F1"), type0)

    resources = COSDictionary()
    resources.set_item(_FONT, fonts)
    return resources


def _extract_font_file2(page_dict: COSDictionary) -> bytes | None:
    """Walk a page dict's /Resources/Font/F1/DescendantFonts[0]/FontDescriptor
    /FontFile2 chain; return raw bytes (or None if missing)."""
    res = page_dict.get_dictionary_object(_RESOURCES)
    if not isinstance(res, COSDictionary):
        return None
    fonts = res.get_dictionary_object(_FONT)
    if not isinstance(fonts, COSDictionary):
        return None
    f1 = fonts.get_dictionary_object(COSName.get_pdf_name("F1"))
    if not isinstance(f1, COSDictionary):
        return None
    descendants = f1.get_dictionary_object(_DESCENDANT_FONTS)
    if not isinstance(descendants, COSArray) or descendants.size() == 0:
        return None
    cid = descendants.get_object(0)
    if not isinstance(cid, COSDictionary):
        return None
    descriptor = cid.get_dictionary_object(_FONT_DESCRIPTOR)
    if not isinstance(descriptor, COSDictionary):
        return None
    ff2 = descriptor.get_dictionary_object(_FONT_FILE2)
    if not isinstance(ff2, COSStream):
        return None
    return ff2.get_raw_data()


# ---------- /FontFile2 preserved across split ----------


def test_cid_subset_program_preserved_in_split_chunk() -> None:
    page = PDPage()
    page.get_cos_object().set_item(_RESOURCES, _make_cid_font_resources())
    _attach_f1_content(page)

    src = PDDocument()
    src.add_page(page)

    chunks = Splitter().split(src)
    assert len(chunks) == 1

    chunk_page_dict = chunks[0].get_pages().get(0).get_cos_object()
    extracted = _extract_font_file2(chunk_page_dict)
    assert extracted == _SUBSET_BYTES, (
        "FontFile2 subset program was truncated or lost during split"
    )
    chunks[0].close()
    src.close()


def test_cid_subset_program_preserved_across_multi_chunk_split() -> None:
    """Two pages, each with its own embedded CID subset, split into
    separate chunks. Both subsets must arrive intact."""
    page1 = PDPage()
    page1.get_cos_object().set_item(_RESOURCES, _make_cid_font_resources())
    _attach_f1_content(page1)
    page2 = PDPage()
    page2.get_cos_object().set_item(_RESOURCES, _make_cid_font_resources())
    _attach_f1_content(page2)

    src = PDDocument()
    src.add_page(page1)
    src.add_page(page2)

    chunks = Splitter().split(src)
    assert len(chunks) == 2
    for chunk in chunks:
        page_dict = chunk.get_pages().get(0).get_cos_object()
        assert _extract_font_file2(page_dict) == _SUBSET_BYTES
        chunk.close()
    src.close()


def test_cid_subset_round_trips_through_save_load() -> None:
    """The subset program survives the full save → reload cycle."""
    page = PDPage()
    page.get_cos_object().set_item(_RESOURCES, _make_cid_font_resources())
    _attach_f1_content(page)
    src = PDDocument()
    src.add_page(page)

    chunks = Splitter().split(src)
    sink = io.BytesIO()
    chunks[0].save(sink)
    chunks[0].close()
    src.close()

    with PDDocument.load(sink.getvalue()) as reloaded:
        page_dict = reloaded.get_pages().get(0).get_cos_object()
        # Walk the chain — note the post-reload streams come back through
        # the parser, so we compare against expected bytes.
        extracted = _extract_font_file2(page_dict)
        assert extracted == _SUBSET_BYTES


# ---------- font is independent of source after split ----------


def test_split_chunk_font_dict_is_independent_of_source() -> None:
    """Mutating the split chunk's font descriptor must not leak back
    into the source document — import_page deep-copies the resource
    chain."""
    page = PDPage()
    page.get_cos_object().set_item(_RESOURCES, _make_cid_font_resources())
    _attach_f1_content(page)
    src = PDDocument()
    src.add_page(page)

    src_page_dict = src.get_pages().get(0).get_cos_object()
    src_subset_before = _extract_font_file2(src_page_dict)

    chunks = Splitter().split(src)
    chunk_page_dict = chunks[0].get_pages().get(0).get_cos_object()

    # Mutate chunk's FontFile2 metadata.
    chunk_descriptor = (
        chunk_page_dict.get_dictionary_object(_RESOURCES)
        .get_dictionary_object(_FONT)
        .get_dictionary_object(COSName.get_pdf_name("F1"))
        .get_dictionary_object(_DESCENDANT_FONTS)
        .get_object(0)
        .get_dictionary_object(_FONT_DESCRIPTOR)
    )
    chunk_descriptor.set_item(
        COSName.get_pdf_name("FontName"),
        COSName.get_pdf_name("XXXXXX+Mutated"),
    )

    # Source descriptor is untouched.
    src_descriptor = (
        src_page_dict.get_dictionary_object(_RESOURCES)
        .get_dictionary_object(_FONT)
        .get_dictionary_object(COSName.get_pdf_name("F1"))
        .get_dictionary_object(_DESCENDANT_FONTS)
        .get_object(0)
        .get_dictionary_object(_FONT_DESCRIPTOR)
    )
    assert (
        src_descriptor.get_name(COSName.get_pdf_name("FontName"))
        == "ABCDEF+NotoSans"
    )
    # Source FontFile2 still intact.
    assert _extract_font_file2(src_page_dict) == src_subset_before
    chunks[0].close()
    src.close()
