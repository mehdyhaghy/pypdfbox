"""Wave 1595 — ``PDFMarkedContentExtractor._dispatch_marked`` BMC/BDC parity.

Closes the wave-1535 DEFERRED divergence for the ``text/`` engine: the
extractor's inline ``_dispatch_marked`` previously

(a) took ``operands[0]`` as the ``BMC`` tag instead of the *last*
    ``COSName`` upstream ``BeginMarkedContentSequence.process`` keeps, and
(b) pushed a marked-content node for an unresolved/invalid ``BDC``
    property list where upstream
    ``BeginMarkedContentSequenceWithProperties.process`` returns *without*
    opening a sequence (the ``propDict == null`` / non-name-tag branches).

The distinction between the two operators is deliberate and preserved:

* ``BMC`` / ``MP`` — tag is the *last* ``COSName`` (leading junk skipped).
* ``BDC`` / ``DP`` — tag is ``operands[0]`` (the *first* operand); when
  the tag is not a name or the property list cannot be resolved to a
  dictionary, no sequence/point is opened.

These tests drive the extractor's inline ``_dispatch_marked`` directly
(and via full content streams) and cross-check against the shared
``_props.extract_tag`` reference used by the registered operators.
"""
from __future__ import annotations

from pypdfbox.contentstream.operator.markedcontent._props import extract_tag
from pypdfbox.cos import (
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFMarkedContentExtractor
from pypdfbox.text.pdf_text_stripper import _TextState


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _extractor() -> PDFMarkedContentExtractor:
    return PDFMarkedContentExtractor()


def _dispatch(extractor: PDFMarkedContentExtractor, op: str, operands: list) -> None:
    extractor._dispatch_marked(op, operands, _TextState())


def _stack(extractor: PDFMarkedContentExtractor) -> list:
    return list(extractor._current_marked_contents)


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---- BMC: last COSName wins ------------------------------------------

def test_bmc_single_name_tag():
    e = _extractor()
    _dispatch(e, "BMC", [_name("Span")])
    assert _stack(e)[-1].get_tag() == "Span"


def test_bmc_tag_is_last_name_after_junk():
    # 1 (x) /Artifact BMC -> opens /Artifact, not None.
    e = _extractor()
    ops = [COSInteger.get(1), COSString("x"), _name("Artifact")]
    _dispatch(e, "BMC", ops)
    assert _stack(e)[-1].get_tag() == "Artifact"


def test_bmc_two_names_last_wins():
    e = _extractor()
    _dispatch(e, "BMC", [_name("A"), _name("B")])
    assert _stack(e)[-1].get_tag() == "B"


def test_bmc_inline_matches_extract_tag_junk_then_name():
    ops = [COSInteger.get(1), COSString("x"), _name("Artifact")]
    e = _extractor()
    _dispatch(e, "BMC", ops)
    selected = extract_tag(ops)
    assert _stack(e)[-1].get_tag() == (selected.get_name() if selected else None)


def test_bmc_no_name_yields_none_tag_but_opens_sequence():
    # Upstream BMC tolerates a null tag (proceeds); only BDC requires a
    # resolvable property list.
    e = _extractor()
    _dispatch(e, "BMC", [COSInteger.get(1), COSString("nope")])
    assert len(_stack(e)) == 1
    assert _stack(e)[-1].get_tag() is None


# ---- BDC: tag is operands[0]; unresolved props -> NO node ------------

def test_bdc_valid_inline_dict_opens_node():
    e = _extractor()
    props = COSDictionary()
    props.set_item(_name("MCID"), COSInteger.get(7))
    _dispatch(e, "BDC", [_name("Span"), props])
    assert len(_stack(e)) == 1
    assert _stack(e)[-1].get_tag() == "Span"
    assert _stack(e)[-1].get_mcid() == 7


def test_bdc_tag_is_first_operand_not_last_name():
    # /Figure /PropList BDC — operands[1] is a property-list NAME, not the
    # tag. The named list is unresolvable here, so no node opens; but the
    # selected tag (had it resolved) is operands[0].
    e = _extractor()
    ops = [_name("Figure"), _name("PropList")]
    _dispatch(e, "BDC", ops)
    # unresolved /PropList -> upstream returns without opening.
    assert _stack(e) == []


def test_bdc_unresolved_named_property_opens_no_node():
    # No active page / no resources -> the named property list cannot be
    # resolved; upstream BeginMarkedContentSequenceWithProperties returns
    # WITHOUT opening a sequence (propDict == null).
    e = _extractor()
    _dispatch(e, "BDC", [_name("P"), _name("MissingProps")])
    assert _stack(e) == []


def test_bdc_first_operand_not_name_opens_no_node():
    # operands[0] is not a COSName -> upstream returns immediately.
    e = _extractor()
    props = COSDictionary()
    _dispatch(e, "BDC", [COSInteger.get(1), props])
    assert _stack(e) == []


def test_bdc_missing_property_operand_opens_no_node():
    # Only one operand -> resolve_property_dict returns None -> no node.
    e = _extractor()
    _dispatch(e, "BDC", [_name("Span")])
    assert _stack(e) == []


# ---- DP: marked-content point, same tag/property rules ---------------

def test_dp_unresolved_property_is_noop():
    # DP never opens a sequence; with an unresolved property list it must
    # also not raise and the stack stays empty.
    e = _extractor()
    _dispatch(e, "DP", [_name("P"), _name("MissingProps")])
    assert _stack(e) == []


# ---- nested + EMC balance --------------------------------------------

def test_nested_bmc_then_valid_bdc_then_emc_balance():
    e = _extractor()
    _dispatch(e, "BMC", [COSInteger.get(0), _name("Outer")])
    props = COSDictionary()
    props.set_item(_name("MCID"), COSInteger.get(3))
    _dispatch(e, "BDC", [_name("Inner"), props])
    assert [m.get_tag() for m in _stack(e)] == ["Outer", "Inner"]
    _dispatch(e, "EMC", [])
    assert [m.get_tag() for m in _stack(e)] == ["Outer"]
    _dispatch(e, "EMC", [])
    assert _stack(e) == []


def test_skipped_bdc_emc_pops_parent_like_upstream():
    # When BDC is skipped (unresolved props) the matching EMC pops the
    # OPEN parent, mirroring upstream's no-underflow endMarkedContentSequence
    # (the stack count drifts but never goes negative).
    e = _extractor()
    _dispatch(e, "BMC", [_name("Outer")])
    _dispatch(e, "BDC", [_name("Inner"), _name("Unresolved")])  # skipped
    assert [m.get_tag() for m in _stack(e)] == ["Outer"]
    _dispatch(e, "EMC", [])  # the Inner's EMC pops Outer
    assert _stack(e) == []
    _dispatch(e, "EMC", [])  # the Outer's EMC -> no-op on empty stack
    assert _stack(e) == []


def test_emc_on_empty_stack_is_noop():
    e = _extractor()
    _dispatch(e, "EMC", [])
    assert _stack(e) == []


# ---- end-to-end content stream: unresolved BDC drops no node ---------

def test_process_page_unresolved_bdc_name_opens_no_marked_content():
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"/P /MissingProps BDC\n"
        b"BT /F0 12 Tf 0 0 Td (Hello) Tj ET\n"
        b"EMC\n",
    )
    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.process_page(page)
    # Unresolved /MissingProps -> upstream opens no sequence, so the page
    # has no top-level marked content (the text falls outside any bucket).
    assert extractor.get_marked_contents() == []


def test_process_page_bmc_last_name_tag_end_to_end():
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"1 (x) /Artifact BMC\n"
        b"BT /F0 12 Tf 0 0 Td (Hello) Tj ET\n"
        b"EMC\n",
    )
    extractor = PDFMarkedContentExtractor()
    extractor.set_suppress_duplicate_overlapping_text(False)
    extractor.process_page(page)
    contents = extractor.get_marked_contents()
    assert len(contents) == 1
    assert contents[0].get_tag() == "Artifact"
