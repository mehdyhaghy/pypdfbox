from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFCatalog, FDFDictionary, FDFField


def test_catalog_presence_and_clear_helpers_do_not_hide_malformed_fdf() -> None:
    catalog = FDFCatalog()
    assert catalog.has_fdf() is False

    fdf = catalog.get_fdf()
    assert catalog.has_fdf() is True
    assert catalog.get_fdf() is fdf

    catalog.clear_fdf()
    assert catalog.has_fdf() is False
    assert not catalog.get_cos_object().contains_key(COSName.get_pdf_name("FDF"))

    catalog.get_cos_object().set_item(
        COSName.get_pdf_name("FDF"), COSName.get_pdf_name("Bad")
    )
    assert catalog.has_fdf() is False
    replacement = catalog.get_fdf()
    assert replacement.get_cos_object().is_empty()
    assert catalog.has_fdf() is True

    catalog.set_version("1.3")
    assert catalog.has_version() is True
    catalog.clear_version()
    assert catalog.has_version() is False


def test_dictionary_presence_and_clear_helpers_are_typed() -> None:
    fdf = FDFDictionary()
    field = FDFField()
    annotation = FDFAnnotation()
    ids = COSArray([COSString(b"abc"), COSString(b"def")])
    embedded = COSArray()

    fdf.set_fields([field])
    fdf.set_annotations([annotation])
    fdf.set_file("source.pdf")
    fdf.set_id(ids)
    fdf.set_status("ready")
    fdf.set_encoding("UTF-8")
    fdf.set_target("target")
    fdf.set_embedded_fdfs(embedded)

    assert fdf.has_fields() is True
    assert fdf.has_annotations() is True
    assert fdf.has_file() is True
    assert fdf.has_id() is True
    assert fdf.has_status() is True
    assert fdf.has_encoding() is True
    assert fdf.has_target() is True
    assert fdf.has_embedded_fdfs() is True

    fdf.clear_fields()
    fdf.clear_annotations()
    fdf.clear_file()
    fdf.clear_id()
    fdf.clear_status()
    fdf.clear_encoding()
    fdf.clear_target()
    fdf.clear_embedded_fdfs()

    assert fdf.has_fields() is False
    assert fdf.has_annotations() is False
    assert fdf.has_file() is False
    assert fdf.has_id() is False
    assert fdf.has_status() is False
    assert fdf.has_encoding() is False
    assert fdf.has_target() is False
    assert fdf.has_embedded_fdfs() is False

    raw = fdf.get_cos_object()
    raw.set_item(COSName.get_pdf_name("Fields"), COSName.get_pdf_name("Bad"))
    raw.set_item(COSName.get_pdf_name("Annots"), COSName.get_pdf_name("Bad"))
    raw.set_item(COSName.get_pdf_name("ID"), COSName.get_pdf_name("Bad"))
    raw.set_item(COSName.get_pdf_name("EmbeddedFDFs"), COSName.get_pdf_name("Bad"))

    assert fdf.has_fields() is False
    assert fdf.get_fields() is None
    assert fdf.has_annotations() is False
    assert fdf.get_annotations() is None
    assert fdf.has_id() is False
    assert fdf.get_id() is None
    assert fdf.has_embedded_fdfs() is False
    assert fdf.get_embedded_fdfs() is None


def test_field_presence_and_clear_helpers() -> None:
    field = FDFField()
    child = FDFField()
    options = COSArray([COSString("one"), COSString("two")])

    field.set_partial_field_name("name")
    field.set_value("value")
    field.set_default_value("default")
    field.set_kids([child])
    field.set_mapping_name("mapping")
    field.get_cos_object().set_item(COSName.get_pdf_name("Opt"), options)

    assert field.has_partial_field_name() is True
    assert field.has_value() is True
    assert field.has_default_value() is True
    assert field.has_kids() is True
    assert field.has_mapping_name() is True
    assert field.has_options() is True

    field.clear_partial_field_name()
    field.clear_value()
    field.clear_default_value()
    field.clear_kids()
    field.clear_mapping_name()
    field.clear_options()

    assert field.has_partial_field_name() is False
    assert field.has_value() is False
    assert field.has_default_value() is False
    assert field.has_kids() is False
    assert field.has_mapping_name() is False
    assert field.has_options() is False

    field.get_cos_object().set_item(
        COSName.get_pdf_name("Kids"), COSName.get_pdf_name("Bad")
    )
    field.get_cos_object().set_item(
        COSName.get_pdf_name("Opt"), COSName.get_pdf_name("Bad")
    )
    assert field.has_kids() is False
    assert field.get_kids() is None
    assert field.has_options() is False
    assert field.get_options() is None


def test_annotation_common_presence_clear_and_malformed_numeric_arrays() -> None:
    annotation = FDFAnnotation()
    annotation.set_page(2)
    annotation.set_name("annot-1")
    annotation.set_contents("contents")
    annotation.set_title("title")
    annotation.set_subtype("Text")
    annotation.set_rectangle((1.0, 2.0, 3.0, 4.0))
    annotation.set_color((0.1, 0.2, 0.3))
    annotation.set_flags(7)
    annotation.set_name_attribute("Note")
    annotation.set_modified_date("D:20260508120000Z")

    assert annotation.has_page() is True
    assert annotation.has_name() is True
    assert annotation.has_contents() is True
    assert annotation.has_title() is True
    assert annotation.has_subtype() is True
    assert annotation.has_rectangle() is True
    assert annotation.has_color() is True
    assert annotation.has_flags() is True
    assert annotation.has_name_attribute() is True
    assert annotation.has_modified_date() is True

    annotation.clear_page()
    annotation.clear_name()
    annotation.clear_contents()
    annotation.clear_title()
    annotation.clear_subtype()
    annotation.clear_rectangle()
    annotation.clear_color()
    annotation.clear_flags()
    annotation.clear_name_attribute()
    annotation.clear_modified_date()

    assert annotation.has_page() is False
    assert annotation.has_name() is False
    assert annotation.has_contents() is False
    assert annotation.has_title() is False
    assert annotation.has_subtype() is False
    assert annotation.has_rectangle() is False
    assert annotation.has_color() is False
    assert annotation.has_flags() is False
    assert annotation.has_name_attribute() is False
    assert annotation.has_modified_date() is False

    raw = annotation.get_cos_object()
    raw.set_item(
        COSName.get_pdf_name("Rect"),
        COSArray(
            [
                COSInteger.get(1),
                COSInteger.get(2),
                COSName.get_pdf_name("Bad"),
                COSInteger.get(4),
            ]
        ),
    )
    raw.set_item(
        COSName.get_pdf_name("C"),
        COSArray([COSInteger.get(1), COSName.get_pdf_name("Bad"), COSInteger.get(3)]),
    )
    raw.set_item(COSName.get_pdf_name("Page"), COSName.get_pdf_name("Bad"))
    raw.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("Bad"))

    assert annotation.get_rectangle() is None
    assert annotation.has_rectangle() is False
    assert annotation.get_color() is None
    assert annotation.has_color() is False
    assert annotation.has_page() is False
    assert annotation.get_page() == -1
    assert annotation.has_flags() is False
    assert annotation.get_flags() == 0
