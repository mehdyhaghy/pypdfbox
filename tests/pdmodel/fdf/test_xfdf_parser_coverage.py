"""Coverage backfill for :mod:`pypdfbox.pdmodel.fdf.xfdf_parser`.

Targets the annotation-factory branches (caret, fileattachment, polyline,
ink, stamp), the optional-attribute setters on
``_populate_annotation_base`` (page, date, flags, color, rect, creation
date, opacity, subject, intent, contents, contents-richtext), the
populate_field_from_xfdf rich-text path, and the lenient error-handling
``except`` blocks in :func:`populate_fdf_dictionary_from_xfdf`.
"""

from __future__ import annotations

from xml.dom.minidom import parseString

import pytest

from pypdfbox.pdmodel.fdf import FDFDocument
from pypdfbox.pdmodel.fdf.fdf_annotation_caret import FDFAnnotationCaret
from pypdfbox.pdmodel.fdf.fdf_annotation_file_attachment import (
    FDFAnnotationFileAttachment,
)
from pypdfbox.pdmodel.fdf.fdf_annotation_ink import FDFAnnotationInk
from pypdfbox.pdmodel.fdf.fdf_annotation_polyline import FDFAnnotationPolyline
from pypdfbox.pdmodel.fdf.fdf_annotation_square import FDFAnnotationSquare
from pypdfbox.pdmodel.fdf.fdf_annotation_stamp import FDFAnnotationStamp
from pypdfbox.pdmodel.fdf.fdf_annotation_text import FDFAnnotationText
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.fdf.xfdf_parser import (
    build_annotation_from_xfdf,
    populate_fdf_dictionary_from_xfdf,
    populate_field_from_xfdf,
)


def _annot_element(xml: str):
    """Return the inner ``<annots>`` first-child element."""
    doc = parseString(xml)
    return doc.documentElement


# --- Annotation factory branch coverage ----------------------------------


def test_build_caret_annotation() -> None:
    el = _annot_element('<caret page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationCaret)


def test_build_file_attachment_annotation() -> None:
    el = _annot_element('<fileattachment page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationFileAttachment)


def test_build_polyline_annotation() -> None:
    el = _annot_element('<polyline page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationPolyline)


def test_build_ink_annotation() -> None:
    el = _annot_element('<ink page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationInk)


def test_build_stamp_annotation() -> None:
    el = _annot_element('<stamp page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationStamp)


def test_build_text_annotation() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationText)


def test_build_square_annotation_via_fringe() -> None:
    el = _annot_element('<square page="0" rect="0,0,10,10" fringe="1,2,3,4"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationSquare)


def test_build_unknown_annotation_returns_none() -> None:
    el = _annot_element('<bogus page="0" rect="0,0,10,10"/>')
    assert build_annotation_from_xfdf(el) is None


# --- _populate_annotation_base lenient parsing branches -------------------


def test_invalid_page_attribute_logged_but_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    el = _annot_element('<text page="not-a-number" rect="0,0,10,10"/>')
    caplog.set_level("WARNING")
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationText)
    assert any("non-integer" in rec.getMessage() for rec in caplog.records)


def test_color_attribute_parsed() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10" color="#80ff40"/>')
    annot = build_annotation_from_xfdf(el)
    color = annot.get_color()  # type: ignore[union-attr]
    assert color is not None


def test_invalid_color_silently_skipped() -> None:
    # Invalid hex falls into the ``except ValueError: pass`` branch.
    el = _annot_element('<text page="0" rect="0,0,10,10" color="#ZZZZZZ"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot is not None  # no raise


def test_date_attribute_set() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10" date="D:20240101"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot.get_date() == "D:20240101"  # type: ignore[union-attr]


def test_flags_attribute_sets_all_flag_setters() -> None:
    flags = "invisible,hidden,print,nozoom,norotate,noview,readonly,locked,togglenoview"
    el = _annot_element(
        f'<text page="0" rect="0,0,10,10" flags="{flags}"/>'
    )
    annot = build_annotation_from_xfdf(el)
    assert annot is not None
    # ``readonly`` ⇒ /F bit. We mainly care that no exception is raised
    # exercising each branch of the flag_map dispatch.


def test_flags_attribute_ignores_unknown_tokens() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10" flags="bogus, , print"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot is not None


def test_name_attribute_sets_unique_name() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10" name="annot-1"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot.get_name() == "annot-1"  # type: ignore[union-attr]


def test_invalid_rect_attribute_silently_skipped() -> None:
    # parse_rectangle_attributes raises OSError on wrong count.
    el = _annot_element('<text page="0" rect="1,2,3"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot is not None  # no raise


def test_title_attribute_set() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10" title="Alice"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot.get_title() == "Alice"  # type: ignore[union-attr]


def test_creation_date_attribute_set() -> None:
    el = _annot_element(
        '<text page="0" rect="0,0,10,10" creationdate="D:20230101000000"/>'
    )
    annot = build_annotation_from_xfdf(el)
    # set_creation_date parses the PDF date string into a datetime;
    # the round-tripped value must reflect the supplied year.
    parsed = annot.get_creation_date()  # type: ignore[union-attr]
    assert parsed is not None
    assert getattr(parsed, "year", None) == 2023


def test_opacity_attribute_parsed() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10" opacity="0.5"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot.get_opacity() == pytest.approx(0.5)  # type: ignore[union-attr]


def test_invalid_opacity_silently_skipped() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10" opacity="abc"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot is not None  # no raise


def test_subject_attribute_set() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10" subject="my subject"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot.get_subject() == "my subject"  # type: ignore[union-attr]


def test_intent_attribute_set_via_lower_case() -> None:
    el = _annot_element('<text page="0" rect="0,0,10,10" intent="FreeTextCallout"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot.get_intent() == "FreeTextCallout"  # type: ignore[union-attr]


def test_intent_attribute_set_via_uppercase_it_alias() -> None:
    # ``IT`` alias used when ``intent`` is empty.
    el = _annot_element('<text page="0" rect="0,0,10,10" IT="FreeTextCallout"/>')
    annot = build_annotation_from_xfdf(el)
    assert annot.get_intent() == "FreeTextCallout"  # type: ignore[union-attr]


def test_contents_child_element_sets_contents() -> None:
    el = _annot_element(
        '<text page="0" rect="0,0,10,10"><contents>hello world</contents></text>'
    )
    annot = build_annotation_from_xfdf(el)
    assert annot.get_contents() == "hello world"  # type: ignore[union-attr]


def test_contents_richtext_child_sets_rich_contents() -> None:
    el = _annot_element(
        '<text page="0" rect="0,0,10,10">'
        '<contents-richtext>  hello rich  </contents-richtext>'
        '</text>'
    )
    annot = build_annotation_from_xfdf(el)
    assert annot is not None
    # Plain /Contents is the stripped form.
    assert annot.get_contents() == "hello rich"  # type: ignore[union-attr]


# --- populate_field_from_xfdf rich-text branch ----------------------------


def test_field_with_rich_text_value() -> None:
    el = _annot_element(
        '<field name="myfield">'
        '<value-richtext>rich body</value-richtext>'
        '</field>'
    )
    field = FDFField()
    populate_field_from_xfdf(field, el)
    rt = field.get_rich_text()
    assert rt is not None


def test_field_with_plain_value() -> None:
    el = _annot_element(
        '<field name="myfield"><value>plain val</value></field>'
    )
    field = FDFField()
    populate_field_from_xfdf(field, el)
    assert field.get_partial_field_name() == "myfield"
    assert field.get_value() == "plain val"


def test_field_with_nested_kids() -> None:
    el = _annot_element(
        '<field name="parent">'
        '<field name="child"><value>cv</value></field>'
        '</field>'
    )
    field = FDFField()
    populate_field_from_xfdf(field, el)
    kids = field.get_kids()
    assert kids is not None and len(kids) == 1
    assert kids[0].get_partial_field_name() == "child"


# --- populate_fdf_dictionary_from_xfdf error-handling branches ------------


def test_ids_with_invalid_original_logged_but_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><ids original="NOTHEXNOTHEX" modified="CAFEBABE"/></xfdf>'
    )
    caplog.set_level("WARNING")
    fdf = FDFDocument()
    try:
        fdf.set_xfdf(sample)
        ids = fdf.get_catalog().get_fdf().get_id()
        # The modified entry should still be stored.
        assert ids is not None
        # Warning about 'original' should have been logged.
        assert any("'original'" in rec.getMessage() for rec in caplog.records)
    finally:
        fdf.close()


def test_ids_with_invalid_modified_logged_but_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><ids original="DEADBEEF" modified="NOPENOPENOPE"/></xfdf>'
    )
    caplog.set_level("WARNING")
    fdf = FDFDocument()
    try:
        fdf.set_xfdf(sample)
        assert any("'modified'" in rec.getMessage() for rec in caplog.records)
    finally:
        fdf.close()


def test_fields_with_failing_child_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Exercise the ``except OSError`` arm in the fields walker.

    We monkey-patch :func:`populate_field_from_xfdf` to raise OSError on
    the first child, which is the easiest deterministic way to hit the
    swallow branch.
    """
    import pypdfbox.pdmodel.fdf.xfdf_parser as parser_mod

    orig = parser_mod.populate_field_from_xfdf

    def _raising(field: object, element: object) -> None:
        raise OSError("simulated field-parse failure")

    parser_mod.populate_field_from_xfdf = _raising  # type: ignore[assignment]
    try:
        from pypdfbox.pdmodel.fdf.fdf_dictionary import FDFDictionary

        el = _annot_element(
            '<xfdf><fields><field name="bad"/></fields></xfdf>'
        )
        fdf_dict = FDFDictionary()
        caplog.set_level("WARNING")
        populate_fdf_dictionary_from_xfdf(fdf_dict, el)
        assert any("Field ignored" in rec.getMessage() for rec in caplog.records)
    finally:
        parser_mod.populate_field_from_xfdf = orig  # type: ignore[assignment]


def test_freetext_branch_in_annotation_factory() -> None:
    from pypdfbox.pdmodel.fdf.fdf_annotation_free_text import FDFAnnotationFreeText

    el = _annot_element('<freetext page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationFreeText)


def test_circle_branch_in_annotation_factory() -> None:
    from pypdfbox.pdmodel.fdf.fdf_annotation_circle import FDFAnnotationCircle

    el = _annot_element('<circle page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationCircle)


def test_polygon_branch_in_annotation_factory() -> None:
    from pypdfbox.pdmodel.fdf.fdf_annotation_polygon import FDFAnnotationPolygon

    el = _annot_element('<polygon page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationPolygon)


def test_line_branch_in_annotation_factory() -> None:
    from pypdfbox.pdmodel.fdf.fdf_annotation_line import FDFAnnotationLine

    el = _annot_element('<line page="0" rect="0,0,10,10"/>')
    annot = build_annotation_from_xfdf(el)
    assert isinstance(annot, FDFAnnotationLine)


def test_text_markup_branches() -> None:
    from pypdfbox.pdmodel.fdf.fdf_annotation_text_markup import FDFAnnotationTextMarkup

    for tag, expected in [
        ("highlight", "Highlight"),
        ("underline", "Underline"),
        ("strikeout", "StrikeOut"),
        ("squiggly", "Squiggly"),
    ]:
        el = _annot_element(f'<{tag} page="0" rect="0,0,10,10"/>')
        annot = build_annotation_from_xfdf(el)
        assert isinstance(annot, FDFAnnotationTextMarkup)
        assert annot.get_subtype() == expected


# --- _populate_annotation_subtype error-suppress branches ----------------


def test_polygon_invalid_vertices_silently_suppressed() -> None:
    # init_vertices raises OSError on malformed coords ⇒ suppressed.
    el = _annot_element(
        '<polygon page="0" rect="0,0,10,10" vertices="not-coords"/>'
    )
    annot = build_annotation_from_xfdf(el)
    assert annot is not None  # no raise


def test_freetext_valid_callout_wires_through() -> None:
    el = _annot_element(
        '<freetext page="0" rect="0,0,10,10" callout="1,2,3,4,5,6"/>'
    )
    annot = build_annotation_from_xfdf(el)
    callout = annot.get_callout()  # type: ignore[union-attr]
    assert callout == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_polyline_init_styles_branch_wired() -> None:
    el = _annot_element(
        '<polyline page="0" rect="0,0,10,10" head="OpenArrow"/>'
    )
    annot = build_annotation_from_xfdf(el)
    from pypdfbox.pdmodel.fdf.fdf_annotation_polyline import FDFAnnotationPolyline

    assert isinstance(annot, FDFAnnotationPolyline)


# --- populate_fdf_dictionary happy paths (lines 321-323, 355, 366-367) ----


def test_xfdf_f_element_wires_set_file() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><f href="my.pdf"/></xfdf>'
    )
    fdf = FDFDocument()
    try:
        fdf.set_xfdf(sample)
        assert fdf.get_catalog().get_fdf().get_file_path() == "my.pdf"
    finally:
        fdf.close()


def test_xfdf_fields_happy_path_appends() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><fields>'
        b'<field name="a"><value>1</value></field>'
        b'<field name="b"><value>2</value></field>'
        b'</fields></xfdf>'
    )
    fdf = FDFDocument()
    try:
        fdf.set_xfdf(sample)
        fields = fdf.get_catalog().get_fdf().get_fields()
        assert fields is not None and len(fields) == 2
    finally:
        fdf.close()


def test_xfdf_annots_happy_path_appends() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><annots>'
        b'<text page="0" rect="0,0,1,1"/>'
        b'<text page="0" rect="0,0,1,1"/>'
        b"</annots></xfdf>"
    )
    fdf = FDFDocument()
    try:
        fdf.set_xfdf(sample)
        annots = fdf.get_catalog().get_fdf().get_annotations()
        assert annots is not None and len(annots) == 2
    finally:
        fdf.close()


def test_annots_with_failing_child_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Exercise the ``except OSError`` arm in the annotations walker."""
    import pypdfbox.pdmodel.fdf.xfdf_parser as parser_mod

    orig = parser_mod.build_annotation_from_xfdf

    def _raising(element: object) -> object:
        raise OSError("simulated annotation-parse failure")

    parser_mod.build_annotation_from_xfdf = _raising  # type: ignore[assignment]
    try:
        from pypdfbox.pdmodel.fdf.fdf_dictionary import FDFDictionary

        el = _annot_element(
            '<xfdf><annots><text page="0" rect="0,0,1,1"/></annots></xfdf>'
        )
        fdf_dict = FDFDictionary()
        caplog.set_level("WARNING")
        populate_fdf_dictionary_from_xfdf(fdf_dict, el)
        assert any(
            "Annotation ignored" in rec.getMessage() for rec in caplog.records
        )
    finally:
        parser_mod.build_annotation_from_xfdf = orig  # type: ignore[assignment]
