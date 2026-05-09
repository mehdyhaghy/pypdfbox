from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString
from pypdfbox.multipdf import LayerUtility
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _seed_page_contents(page: PDPage, body: bytes = b"q Q\n") -> None:
    stream = COSStream()
    stream.set_raw_data(body)
    page.set_contents(stream)


def _make_doc_with_content(page: PDPage | None = None) -> PDDocument:
    doc = PDDocument()
    page = page if page is not None else PDPage()
    _seed_page_contents(page)
    doc.add_page(page)
    return doc


def test_wave370_wrap_in_save_restore_rejects_malformed_contents() -> None:
    doc = PDDocument()
    page = PDPage()
    page.get_cos_object().set_item(COSName.CONTENTS, COSDictionary())
    doc.add_page(page)

    with pytest.raises(OSError, match="COSDictionary"):
        LayerUtility(doc).wrap_in_save_restore(page)

    doc.close()


def test_wave370_import_page_as_form_rejects_unknown_page_selector() -> None:
    source = _make_doc_with_content()
    target = PDDocument()

    with pytest.raises(TypeError, match="PDPage or int"):
        LayerUtility(target).import_page_as_form(source, object())

    source.close()
    target.close()


def test_wave370_import_page_as_form_transfers_only_page_to_form_keys() -> None:
    page = PDPage()
    source = _make_doc_with_content(page)
    target = PDDocument()
    util = LayerUtility(target)

    group = COSDictionary()
    group.set_name("S", "Transparency")
    metadata = COSStream()
    metadata.set_raw_data(b"<x:xmpmeta/>")
    page_dict = page.get_cos_object()
    page_dict.set_item("Group", group)
    page_dict.set_item("LastModified", COSString("D:20260508000000Z"))
    page_dict.set_item("Metadata", metadata)
    page_dict.set_int("StructParents", 12)

    form = util.import_page_as_form(source, 0)
    form_dict = form.get_cos_object()

    assert isinstance(form_dict.get_dictionary_object("Group"), COSDictionary)
    assert form_dict.get_dictionary_object("Group") is not group
    assert form_dict.get_string("LastModified") == "D:20260508000000Z"
    assert isinstance(form_dict.get_dictionary_object("Metadata"), COSStream)
    assert form_dict.get_dictionary_object("Metadata") is not metadata
    assert form_dict.get_dictionary_object("StructParents") is None

    source.close()
    target.close()


def test_wave370_import_page_as_form_merges_into_existing_oc_properties() -> None:
    source = _make_doc_with_content()
    source_props = PDOptionalContentProperties()
    source_group = PDOptionalContentGroup("source-wave370")
    source_props.add_group(source_group)
    source_props.set_group_enabled(source_group, False)
    source.get_document_catalog().set_oc_properties(source_props)

    target = PDDocument()
    target_props = PDOptionalContentProperties()
    target_props.add_group(PDOptionalContentGroup("target-wave370"))
    target.get_document_catalog().set_oc_properties(target_props)

    LayerUtility(target).import_page_as_form(source, 0)

    out_props = target.get_document_catalog().get_oc_properties()
    assert out_props is not None
    assert out_props.has_group("target-wave370") is True
    assert out_props.has_group("source-wave370") is True
    assert out_props.is_group_enabled("source-wave370") is False

    source.close()
    target.close()


def test_wave370_import_page_as_form_copies_oc_properties_into_empty_target() -> None:
    source = _make_doc_with_content()
    source_props = PDOptionalContentProperties()
    source_group = PDOptionalContentGroup("cloned-wave370")
    source_props.add_group(source_group)
    source_props.set_group_enabled(source_group, False)
    source.get_document_catalog().set_oc_properties(source_props)
    target = PDDocument()

    LayerUtility(target).import_page_as_form(source, 0)

    out_props = target.get_document_catalog().get_oc_properties()
    assert out_props is not None
    assert out_props.has_group("cloned-wave370") is True
    assert out_props.is_group_enabled("cloned-wave370") is False

    source.close()
    target.close()


def test_wave370_append_form_as_layer_warns_for_negative_crop_identity(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = _make_doc_with_content()
    target_page = PDPage(PDRectangle(-10.0, -20.0, 100.0, 100.0))
    target = _make_doc_with_content(target_page)
    util = LayerUtility(target)
    form = util.import_page_as_form(source, 0)

    with caplog.at_level("WARNING", logger="pypdfbox.multipdf.layer_utility"):
        util.append_form_as_layer(target_page, form, None, "negative-wave370")

    assert "Negative cropBox" in caplog.text

    source.close()
    target.close()


def test_wave370_append_form_as_layer_rejects_short_transform() -> None:
    source = _make_doc_with_content()
    target = _make_doc_with_content()
    util = LayerUtility(target)
    form = util.import_page_as_form(source, 0)

    with pytest.raises(ValueError, match="exactly 6 numbers"):
        util.append_form_as_layer(target.get_page(0), form, [1.0, 0.0], "bad-matrix")

    source.close()
    target.close()


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [
        (90, [0.0, -0.5, 2.0, 0.0, 0.0, 100.0]),
        (180, [-1.0, 0.0, 0.0, -1.0, 200.0, 100.0]),
        (270, [0.0, 0.5, -2.0, 0.0, 200.0, 0.0]),
    ],
)
def test_wave370_import_page_as_form_sets_quadrant_rotation_matrix(
    rotation: int,
    expected: list[float],
) -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 100.0))
    page.set_rotation(rotation)
    source = _make_doc_with_content(page)
    target = PDDocument()

    form = LayerUtility(target).import_page_as_form(source, 0)

    assert form.get_matrix() == pytest.approx(expected)

    source.close()
    target.close()
