"""Wave 1396 branch-coverage tests for ``xfdf_parser``.

Closes False-branch arrows in
``pypdfbox/pdmodel/fdf/xfdf_parser.py``:

* line 55->54 — non-text / non-CDATA child node skipped in ``_node_text``
* line 80->74 — unknown / repeated tag in ``populate_field_from_xfdf``
* lines 170->176, 215->226, 254->251 — optional attribute absent /
  invalid in ``_populate_annotation_base``
* lines 329->337, 338->346, 346->318, 351->350, 361->318 — XFDF
  ingest branches in ``populate_fdf_dictionary_from_xfdf`` for empty
  attributes, malformed entries, and unknown sub-elements.
"""

from __future__ import annotations

from xml.dom.minidom import parseString

from pypdfbox.pdmodel.fdf.fdf_dictionary import FDFDictionary
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.fdf.xfdf_parser import (
    _node_text,
    build_annotation_from_xfdf,
    populate_fdf_dictionary_from_xfdf,
    populate_field_from_xfdf,
)


def test_node_text_skips_comment_children() -> None:
    """Comment children must be ignored by ``_node_text``.

    Closes the False arm of line 55->54 — a non-TEXT, non-CDATA child
    falls through the loop without contributing to the joined text.
    """
    doc = parseString("<v>Hello<!-- comment -->World</v>")
    text = _node_text(doc.documentElement)
    assert text == "HelloWorld"


def test_populate_field_skips_unknown_child_tag() -> None:
    """Unknown child elements inside ``<field>`` are silently ignored.

    Closes the False arm of line 80->74 — when the inner tag is neither
    ``value``/``value-richtext``/``field`` the loop continues to the
    next sibling.
    """
    doc = parseString(
        '<field name="f1">'
        "<value>v1</value>"
        "<unknown>noise</unknown>"
        "</field>"
    )
    field = FDFField()
    populate_field_from_xfdf(field, doc.documentElement)
    assert field.get_partial_field_name() == "f1"
    assert field.get_value() == "v1"


def test_populate_annotation_base_missing_page_attribute() -> None:
    """No ``page`` attribute leaves page unset.

    Closes the False arm of ``if page`` at line 170->176 — the annotation's
    page index stays at its default after building from XFDF lacking ``page``.
    """
    el = parseString('<text rect="0,0,10,10"/>').documentElement
    annot = build_annotation_from_xfdf(el)
    assert annot is not None
    # Default of -1 means "not set" — set_page() was never invoked.
    assert annot.get_page() == -1


def test_populate_annotation_base_missing_rect_attribute() -> None:
    """No ``rect`` attribute leaves the rectangle unset.

    Closes the False arm of ``if rect`` at line 215->226 — skipping to
    subsequent attribute parsing.
    """
    el = parseString('<text title="t1"/>').documentElement
    annot = build_annotation_from_xfdf(el)
    assert annot is not None
    assert annot.get_title() == "t1"


def test_populate_annotation_base_contents_other_child_skipped() -> None:
    """A non-contents/non-contents-richtext child is ignored.

    Closes the False arm of ``elif child.tagName == "contents-richtext"``
    at line 254->251 — an unknown child returns control to the loop.
    """
    el = parseString(
        '<text><popup>noise</popup><contents>hello</contents></text>'
    ).documentElement
    annot = build_annotation_from_xfdf(el)
    assert annot is not None
    assert annot.get_contents() == "hello"


def test_populate_fdf_dictionary_ids_empty_attributes_skipped() -> None:
    """``<ids>`` without ``original`` / ``modified`` attributes contributes
    no IDs.

    Closes the False arms of ``if original`` (329->337), ``if modified``
    (338->346), and ``if len(ids) > 0`` (346->318) — all three guards
    short-circuit when there's nothing to add.
    """
    fdf_dict = FDFDictionary()
    doc = parseString("<xfdf><ids/></xfdf>")
    populate_fdf_dictionary_from_xfdf(fdf_dict, doc.documentElement)
    # No ID set — the cos dictionary stays absent /ID.
    assert fdf_dict.get_id() is None


def test_populate_fdf_dictionary_fields_unknown_child_skipped() -> None:
    """``<fields>`` with a child whose tagName is not ``field`` is skipped.

    Closes the False arm of ``if f.tagName == "field"`` at line 351->350.
    """
    fdf_dict = FDFDictionary()
    doc = parseString(
        "<xfdf><fields>"
        "<other>x</other>"
        "<field name='f'><value>v</value></field>"
        "</fields></xfdf>"
    )
    populate_fdf_dictionary_from_xfdf(fdf_dict, doc.documentElement)
    fields = fdf_dict.get_fields()
    assert fields is not None
    assert len(fields) == 1
    assert fields[0].get_partial_field_name() == "f"


def test_populate_fdf_dictionary_annots_unknown_tag_returns_none() -> None:
    """Unknown annotation tag yields ``None`` and is filtered out.

    Closes the False arm of ``if built is not None`` at line 361->318
    inside the ``annots`` loop — an unknown subtype results in nothing
    appended.
    """
    fdf_dict = FDFDictionary()
    doc = parseString(
        "<xfdf><annots>"
        "<not-an-annot/>"  # build returns None
        "<text rect='0,0,10,10'/>"
        "</annots></xfdf>"
    )
    populate_fdf_dictionary_from_xfdf(fdf_dict, doc.documentElement)
    annots = fdf_dict.get_annotations()
    assert annots is not None
    # Only the recognised <text> annotation made it through.
    assert len(annots) == 1
