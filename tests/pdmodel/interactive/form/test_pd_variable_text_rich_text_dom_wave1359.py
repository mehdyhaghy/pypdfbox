"""``PDVariableText`` rich-text ``/RV`` DOM serialization — wave 1359.

Closes the long-standing deferred-surface item from CHANGES.md:236:
``PDTextField`` rich-text DOM serialization to ``/RV``. The wave-1330-era
implementation stored ``/RV`` as a raw UTF-8 string; PDF spec ISO 32000-1
§12.7.3.4 mandates XHTML 1.0 for ``/RV`` so we now offer DOM-typed
accessors alongside the existing string surface for back-compat.

This file covers:

* ``set_rich_text_value(Document)`` accepts an :class:`xml.dom.minidom.Document`
  and serializes via ``Document.toxml(encoding="utf-8")``.
* ``get_rich_text_value_as_dom()`` round-trips the structure (elements,
  attributes, nested text) with the standard XHTML tags ``<body>``,
  ``<p>``, ``<b>``, ``<i>``, ``<span style="...">``.
* ``set_rich_text_value_from_dom(None)`` removes the entry, matching
  ``set_rich_text_value(None)`` semantics.
* Inheritable-attribute walk still works on the DOM side (the parent
  field's ``/RV`` is parsed even when the child has no local entry).
* DOCTYPE declarations are rejected as an XXE guard.
* Round-trip survives the full ``COSString`` → save → reparse loop
  via :class:`PDDocument` (mirrors the upstream Java
  ``PDTextFieldTest.testGetRichTextValue`` shape).
"""
from __future__ import annotations

import io
from xml.dom.minidom import Document, parseString

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_FT: COSName = COSName.get_pdf_name("FT")
_RV: COSName = COSName.get_pdf_name("RV")
_KIDS: COSName = COSName.get_pdf_name("Kids")


def _build_sample_dom() -> Document:
    """Build a representative XHTML DOM with the standard /RV tags."""
    dom = parseString(
        "<body>"
        "<p>Plain paragraph.</p>"
        "<p><b>Bold</b> and <i>italic</i> text.</p>"
        '<p><span style="color: red; font-weight: bold">Styled span</span></p>'
        "</body>"
    )
    return dom


# ---------- set_rich_text_value(Document) ----------


def test_set_rich_text_value_accepts_document() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value(_build_sample_dom())

    raw = tf.get_rich_text_value()
    assert raw is not None
    # The XML declaration is included (toxml(encoding="utf-8") emits it).
    assert raw.startswith('<?xml version="1.0" encoding="utf-8"?>')
    assert "<body>" in raw
    assert "<b>Bold</b>" in raw
    assert "<i>italic</i>" in raw
    assert 'style="color: red; font-weight: bold"' in raw


def test_set_rich_text_value_accepts_string_back_compat() -> None:
    """The existing string-based shape continues to work unchanged."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value("<body><p>Hi</p></body>")
    assert tf.get_rich_text_value() == "<body><p>Hi</p></body>"


def test_set_rich_text_value_none_still_removes_entry() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value(_build_sample_dom())
    assert tf.has_rich_text_value() is True
    tf.set_rich_text_value(None)
    assert tf.has_rich_text_value() is False
    assert tf.get_rich_text_value() is None


def test_set_rich_text_value_rejects_non_str_non_document() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    with pytest.raises(TypeError, match="set_rich_text_value expected str or None"):
        tf.set_rich_text_value(42)  # type: ignore[arg-type]


# ---------- get_rich_text_value_as_dom ----------


def test_get_rich_text_value_as_dom_returns_none_when_unset() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.get_rich_text_value_as_dom() is None


def test_get_rich_text_value_as_dom_parses_string_payload() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value("<body><p>Hello <b>world</b></p></body>")

    dom = tf.get_rich_text_value_as_dom()
    assert dom is not None
    body = dom.documentElement
    assert body.tagName == "body"
    p = body.getElementsByTagName("p")[0]
    b = p.getElementsByTagName("b")[0]
    assert b.firstChild is not None
    assert b.firstChild.nodeValue == "world"


def test_get_rich_text_value_as_dom_round_trip_preserves_structure() -> None:
    """Full DOM → /RV → DOM round-trip preserves elements + attributes."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value(_build_sample_dom())

    dom = tf.get_rich_text_value_as_dom()
    assert dom is not None
    body = dom.documentElement
    assert body.tagName == "body"

    paragraphs = body.getElementsByTagName("p")
    assert len(paragraphs) == 3

    # Paragraph 1 — plain text
    assert paragraphs[0].firstChild is not None
    assert paragraphs[0].firstChild.nodeValue == "Plain paragraph."

    # Paragraph 2 — <b> and <i> children
    b_nodes = paragraphs[1].getElementsByTagName("b")
    i_nodes = paragraphs[1].getElementsByTagName("i")
    assert len(b_nodes) == 1
    assert len(i_nodes) == 1
    assert b_nodes[0].firstChild.nodeValue == "Bold"
    assert i_nodes[0].firstChild.nodeValue == "italic"

    # Paragraph 3 — <span style="...">
    span = paragraphs[2].getElementsByTagName("span")[0]
    assert span.getAttribute("style") == "color: red; font-weight: bold"
    assert span.firstChild.nodeValue == "Styled span"


def test_get_rich_text_value_as_dom_from_cos_stream_payload() -> None:
    """``/RV`` stored as ``COSStream`` (spec-allowed) also parses to a DOM."""
    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(_FT, "Tx")
    stream = COSStream()
    with stream.create_output_stream() as sink:
        sink.write(b"<body><p>From stream</p></body>")
    field.set_item(_RV, stream)
    tf = PDTextField(form, field)

    dom = tf.get_rich_text_value_as_dom()
    assert dom is not None
    p = dom.documentElement.getElementsByTagName("p")[0]
    assert p.firstChild.nodeValue == "From stream"


def test_get_rich_text_value_as_dom_inherited_from_parent_walks_chain() -> None:
    """``get_rich_text_value`` walks the inheritable chain; the DOM
    accessor does too because it reads through that getter."""
    form = PDAcroForm()
    form.get_cos_object().set_string(_RV, "<body><p>Inherited</p></body>")

    field = COSDictionary()
    field.set_name(_FT, "Tx")
    tf = PDTextField(form, field)

    dom = tf.get_rich_text_value_as_dom()
    assert dom is not None
    p = dom.documentElement.getElementsByTagName("p")[0]
    assert p.firstChild.nodeValue == "Inherited"


def test_get_rich_text_value_as_dom_rejects_doctype() -> None:
    """Hardened parser: DOCTYPE declarations are an XXE vector and are
    rejected up-front regardless of the underlying minidom backend."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value(
        '<!DOCTYPE html><body><p>Should not parse</p></body>'
    )
    with pytest.raises(OSError, match="DOCTYPE"):
        tf.get_rich_text_value_as_dom()


def test_get_rich_text_value_as_dom_malformed_raises_oserror() -> None:
    """Malformed XML payloads surface as ``OSError`` (parity with the
    project-wide ``XMLUtil.parse`` contract)."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value("<body><p>Unclosed")
    with pytest.raises(OSError):
        tf.get_rich_text_value_as_dom()


# ---------- set_rich_text_value_from_dom ----------


def test_set_rich_text_value_from_dom_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value_from_dom(_build_sample_dom())

    raw = tf.get_rich_text_value()
    assert raw is not None
    assert "<body>" in raw
    assert "<b>Bold</b>" in raw

    # Reparse via the DOM accessor and verify the structure survives.
    dom = tf.get_rich_text_value_as_dom()
    assert dom is not None
    assert len(dom.documentElement.getElementsByTagName("p")) == 3


def test_set_rich_text_value_from_dom_none_removes_entry() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value_from_dom(_build_sample_dom())
    assert tf.has_rich_text_value() is True

    tf.set_rich_text_value_from_dom(None)
    assert tf.has_rich_text_value() is False
    assert tf.get_rich_text_value() is None
    assert tf.get_rich_text_value_as_dom() is None


# ---------- full save → reload round-trip via PDDocument ----------


def test_rich_text_dom_survives_pddocument_save_reload() -> None:
    """End-to-end: build a text field with a DOM-typed /RV, save the
    PDDocument to bytes, reopen, and confirm the DOM is recoverable.

    Mirrors the upstream pattern (``PDTextFieldTest`` round-trip via
    ``PDDocument.save`` / ``PDDocument.load``) — the rich-text payload
    must survive the serialization layer intact."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDocument()
    doc.add_page(PDPage())

    form = PDAcroForm(doc)
    doc.get_document_catalog().set_acro_form(form)

    tf = PDTextField(form)
    tf.set_partial_name("rich_field")
    tf.set_rich_text(True)
    tf.set_rich_text_value(_build_sample_dom())
    form.set_fields([tf])

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()

    buf.seek(0)
    reloaded = PDDocument.load(buf.getvalue())
    try:
        reloaded_form = reloaded.get_document_catalog().get_acro_form()
        assert reloaded_form is not None
        field = reloaded_form.get_field("rich_field")
        assert isinstance(field, PDTextField)

        raw = field.get_rich_text_value()
        assert raw is not None
        assert "<body>" in raw
        assert "<b>Bold</b>" in raw

        dom = field.get_rich_text_value_as_dom()
        assert dom is not None
        paragraphs = dom.documentElement.getElementsByTagName("p")
        assert len(paragraphs) == 3
        # Last paragraph carries the <span style="..."> we built above.
        span = paragraphs[2].getElementsByTagName("span")[0]
        assert span.getAttribute("style") == "color: red; font-weight: bold"
    finally:
        reloaded.close()
