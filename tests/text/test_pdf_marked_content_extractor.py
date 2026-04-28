from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.documentinterchange.markedcontent import PDMarkedContent
from pypdfbox.text import PDFMarkedContentExtractor, TextPosition


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# basic API
# ---------------------------------------------------------------------------


def test_initial_state_has_no_marked_contents() -> None:
    extractor = PDFMarkedContentExtractor()
    assert extractor.get_marked_contents() == []
    assert extractor.is_suppress_duplicate_overlapping_text() is True


def test_suppress_duplicate_overlapping_text_setter_round_trip() -> None:
    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    assert extractor.is_suppress_duplicate_overlapping_text() is False
    extractor.set_suppress_duplicate_overlapping_text(True)
    assert extractor.is_suppress_duplicate_overlapping_text() is True


def test_constructor_accepts_encoding_argument() -> None:
    # API parity: upstream's PDFMarkedContentExtractor(String encoding) is
    # accepted; the encoding is currently unused because pypdfbox decodes
    # via /ToUnicode + /Differences.
    extractor = PDFMarkedContentExtractor("UTF-8")
    assert extractor.get_marked_contents() == []


# ---------------------------------------------------------------------------
# direct callback API (the upstream-named hooks the operator processors
# invoke once they're wired through; tested here without a content stream
# so the bucketing logic is exercised in isolation)
# ---------------------------------------------------------------------------


def test_begin_marked_content_sequence_collects_top_level() -> None:
    from pypdfbox.cos import COSDictionary, COSName

    extractor = PDFMarkedContentExtractor()
    tag = COSName.get_pdf_name("P")
    properties = COSDictionary()
    properties.set_int(COSName.get_pdf_name("MCID"), 7)
    extractor.begin_marked_content_sequence(tag, properties)
    extractor.end_marked_content_sequence()
    contents = extractor.get_marked_contents()
    assert len(contents) == 1
    assert contents[0].get_tag() == "P"
    assert contents[0].get_mcid() == 7


def test_nested_marked_content_attaches_to_parent() -> None:
    from pypdfbox.cos import COSName

    extractor = PDFMarkedContentExtractor()
    parent_tag = COSName.get_pdf_name("Sect")
    child_tag = COSName.get_pdf_name("P")
    extractor.begin_marked_content_sequence(parent_tag, None)
    extractor.begin_marked_content_sequence(child_tag, None)
    extractor.end_marked_content_sequence()
    extractor.end_marked_content_sequence()
    top_level = extractor.get_marked_contents()
    assert len(top_level) == 1
    assert top_level[0].get_tag() == "Sect"
    nested = top_level[0].get_contents()
    assert len(nested) == 1
    assert isinstance(nested[0], PDMarkedContent)
    assert nested[0].get_tag() == "P"


def test_text_buckets_into_currently_open_sequence() -> None:
    from pypdfbox.cos import COSName

    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.begin_marked_content_sequence(
        COSName.get_pdf_name("P"), None
    )
    extractor.process_text_position(
        TextPosition(text="A", x=0.0, y=0.0, font_size=12.0, width=6.0)
    )
    extractor.process_text_position(
        TextPosition(text="B", x=6.0, y=0.0, font_size=12.0, width=6.0)
    )
    extractor.end_marked_content_sequence()
    bucket = extractor.get_marked_contents()[0].get_contents()
    assert [t.get_unicode() for t in bucket] == ["A", "B"]


def test_text_outside_marked_content_is_dropped() -> None:
    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.process_text_position(
        TextPosition(text="X", x=0.0, y=0.0, font_size=12.0, width=6.0)
    )
    assert extractor.get_marked_contents() == []


def test_suppress_duplicate_overlapping_text_collapses_double_strike() -> None:
    from pypdfbox.cos import COSName

    extractor = PDFMarkedContentExtractor()
    assert extractor.is_suppress_duplicate_overlapping_text() is True
    extractor.begin_marked_content_sequence(
        COSName.get_pdf_name("P"), None
    )
    extractor.process_text_position(
        TextPosition(text="A", x=10.0, y=20.0, font_size=12.0, width=6.0)
    )
    # Same glyph at essentially the same coordinates → suppressed.
    extractor.process_text_position(
        TextPosition(text="A", x=10.05, y=20.0, font_size=12.0, width=6.0)
    )
    # Far enough that it's a different rendering.
    extractor.process_text_position(
        TextPosition(text="A", x=50.0, y=20.0, font_size=12.0, width=6.0)
    )
    extractor.end_marked_content_sequence()
    bucket = extractor.get_marked_contents()[0].get_contents()
    assert len(bucket) == 2


def test_marked_content_point_is_no_op() -> None:
    from pypdfbox.cos import COSName

    extractor = PDFMarkedContentExtractor()
    extractor.marked_content_point(COSName.get_pdf_name("Span"), None)
    assert extractor.get_marked_contents() == []


def test_xobject_attaches_to_open_sequence() -> None:
    from pypdfbox.cos import COSName

    extractor = PDFMarkedContentExtractor()
    extractor.begin_marked_content_sequence(
        COSName.get_pdf_name("P"), None
    )
    sentinel = object()
    extractor.xobject(sentinel)
    extractor.end_marked_content_sequence()
    contents = extractor.get_marked_contents()[0].get_contents()
    assert contents == [sentinel]


def test_xobject_outside_sequence_is_dropped() -> None:
    extractor = PDFMarkedContentExtractor()
    extractor.xobject(object())
    assert extractor.get_marked_contents() == []


# ---------------------------------------------------------------------------
# content-stream walk
# ---------------------------------------------------------------------------


def test_process_page_buckets_text_by_mcid_via_bdc_emc() -> None:
    """End-to-end: a tiny content stream with two BDC/EMC sequences, each
    with a different /MCID, should produce two top-level
    PDMarkedContent buckets carrying their respective text."""
    doc = PDDocument()
    body = (
        b"/P <</MCID 0>> BDC\n"
        b"BT /F0 12 Tf 0 0 Td (Hello) Tj ET\n"
        b"EMC\n"
        b"/P <</MCID 1>> BDC\n"
        b"BT /F0 12 Tf 0 -14 Td (World) Tj ET\n"
        b"EMC\n"
    )
    page = _make_page_with_stream(doc, body)
    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.process_page(page)
    contents = extractor.get_marked_contents()
    assert len(contents) == 2
    assert contents[0].get_mcid() == 0
    assert contents[1].get_mcid() == 1
    bucket_0 = [t for t in contents[0].get_contents()
                if isinstance(t, TextPosition)]
    bucket_1 = [t for t in contents[1].get_contents()
                if isinstance(t, TextPosition)]
    assert "".join(t.get_unicode() for t in bucket_0) == "Hello"
    assert "".join(t.get_unicode() for t in bucket_1) == "World"


def test_process_page_handles_nested_bdc() -> None:
    """A BDC nested inside another BDC should attach to its parent
    (via PDMarkedContent.add_marked_content), not the top-level list."""
    doc = PDDocument()
    body = (
        b"/Sect <</MCID 0>> BDC\n"
        b"BT /F0 12 Tf 0 0 Td (Outer) Tj ET\n"
        b"/P <</MCID 1>> BDC\n"
        b"BT /F0 12 Tf 0 -14 Td (Inner) Tj ET\n"
        b"EMC\n"
        b"EMC\n"
    )
    page = _make_page_with_stream(doc, body)
    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.process_page(page)
    top = extractor.get_marked_contents()
    assert len(top) == 1
    assert top[0].get_tag() == "Sect"
    children = top[0].get_contents()
    text_children = [c for c in children if isinstance(c, TextPosition)]
    nested_marks = [c for c in children if isinstance(c, PDMarkedContent)]
    assert "".join(t.get_unicode() for t in text_children) == "Outer"
    assert len(nested_marks) == 1
    assert nested_marks[0].get_tag() == "P"
    inner = [c for c in nested_marks[0].get_contents()
             if isinstance(c, TextPosition)]
    assert "".join(t.get_unicode() for t in inner) == "Inner"


def test_process_page_with_bmc_emc_no_properties() -> None:
    """BMC takes only a tag (no properties); the resulting
    PDMarkedContent should still be created and collect text."""
    doc = PDDocument()
    body = (
        b"/Span BMC\n"
        b"BT /F0 12 Tf 0 0 Td (Plain) Tj ET\n"
        b"EMC\n"
    )
    page = _make_page_with_stream(doc, body)
    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.process_page(page)
    top = extractor.get_marked_contents()
    assert len(top) == 1
    assert top[0].get_tag() == "Span"
    assert top[0].get_mcid() == -1  # no properties → no MCID
    text_children = [c for c in top[0].get_contents()
                     if isinstance(c, TextPosition)]
    assert "".join(t.get_unicode() for t in text_children) == "Plain"


def test_process_page_text_outside_bmc_not_collected() -> None:
    """Text that runs before any BMC/BDC is dropped (no open sequence
    to attach it to). Mirrors upstream behaviour."""
    doc = PDDocument()
    body = (
        b"BT /F0 12 Tf 0 0 Td (Stray) Tj ET\n"
        b"/P <</MCID 0>> BDC\n"
        b"BT /F0 12 Tf 0 -14 Td (Kept) Tj ET\n"
        b"EMC\n"
    )
    page = _make_page_with_stream(doc, body)
    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.process_page(page)
    top = extractor.get_marked_contents()
    assert len(top) == 1
    text_children = [c for c in top[0].get_contents()
                     if isinstance(c, TextPosition)]
    assert "".join(t.get_unicode() for t in text_children) == "Kept"


def test_process_page_empty_stream_returns_empty_list() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(doc, b"")
    extractor = PDFMarkedContentExtractor()
    assert extractor.process_page(page) == ""
    assert extractor.get_marked_contents() == []


def test_process_page_resolves_bdc_named_property_via_resources() -> None:
    """A BDC with a name operand instead of an inline dict resolves the
    name through the page's ``/Resources/Properties`` subdictionary.
    Mirrors upstream's ``PDResources.getPropertyList(name)`` lookup.
    """
    from pypdfbox.cos import COSDictionary, COSInteger, COSName
    from pypdfbox.pdmodel.pd_resources import PDResources

    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"/P /MyProps BDC\n"
        b"BT /F0 12 Tf 0 0 Td (Hello) Tj ET\n"
        b"EMC\n",
    )
    # Wire up the named property list on the page resources.
    res = PDResources()
    cos_props = COSDictionary()
    cos_props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(99))
    res.put(
        COSName.get_pdf_name("Properties"),
        COSName.get_pdf_name("MyProps"),
        cos_props,
    )
    page.set_resources(res)

    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.process_page(page)

    contents = extractor.get_marked_contents()
    assert len(contents) == 1
    assert contents[0].get_tag() == "P"
    assert contents[0].get_mcid() == 99


def test_process_page_dp_marked_point_with_props_does_not_open_sequence() -> None:
    """``DP`` is a single tagged point, not a sequence. It must NOT
    appear in the top-level marked-content list and must NOT swallow the
    surrounding text into a phantom bucket.
    """
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"/P <</MCID 0>> BDC\n"
        b"BT /F0 12 Tf 0 0 Td (Before) Tj ET\n"
        b"/Span <</MCID 7>> DP\n"
        b"BT /F0 12 Tf 0 -14 Td (After) Tj ET\n"
        b"EMC\n",
    )
    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.process_page(page)
    top = extractor.get_marked_contents()
    # Exactly one top-level: the surrounding /P sequence. The DP point is
    # a no-op upstream and produces no bucket.
    assert len(top) == 1
    text = "".join(
        t.get_unicode() for t in top[0].get_contents()
        if isinstance(t, TextPosition)
    )
    assert text == "BeforeAfter"


def test_get_marked_contents_returns_top_level_only_not_nested() -> None:
    """``get_marked_contents`` mirrors upstream — it returns *only* the
    top-level sequences. Nested ones are reachable via the parent's
    ``get_contents()`` list, not the top-level accumulator.
    """
    from pypdfbox.cos import COSName

    extractor = PDFMarkedContentExtractor()
    extractor.begin_marked_content_sequence(
        COSName.get_pdf_name("Sect"), None
    )
    extractor.begin_marked_content_sequence(
        COSName.get_pdf_name("P"), None
    )
    extractor.begin_marked_content_sequence(
        COSName.get_pdf_name("Span"), None
    )
    extractor.end_marked_content_sequence()
    extractor.end_marked_content_sequence()
    extractor.end_marked_content_sequence()
    top = extractor.get_marked_contents()
    assert len(top) == 1
    assert top[0].get_tag() == "Sect"


def test_stray_emc_does_not_raise() -> None:
    """An ``EMC`` without a matching ``BMC``/``BDC`` is silently ignored.
    Mirrors upstream tolerance for malformed input."""
    extractor = PDFMarkedContentExtractor()
    extractor.end_marked_content_sequence()
    extractor.end_marked_content_sequence()
    assert extractor.get_marked_contents() == []
