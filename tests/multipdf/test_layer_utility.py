from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.multipdf import LayerUtility
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def _seed_page_contents(page: PDPage, body: bytes = b"q\n1 0 0 1 0 0 cm Q\n") -> None:
    """Attach a tiny content stream so the page isn't empty (form-import
    needs *something* to copy)."""
    stream = COSStream()
    stream.set_raw_data(body)
    page.set_contents(stream)


def _make_doc_with_one_page() -> PDDocument:
    doc = PDDocument()
    page = PDPage()
    _seed_page_contents(page)
    doc.add_page(page)
    return doc


# ---------- wrap_in_save_restore ----------


def test_wrap_in_save_restore_promotes_single_stream_to_array() -> None:
    """Single-stream /Contents → 3-element array (q, original, Q)."""
    doc = _make_doc_with_one_page()
    page = doc.get_page(0)
    util = LayerUtility(doc)
    util.wrap_in_save_restore(page)
    contents = page.get_cos_object().get_dictionary_object(COSName.CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 3
    # First and last should be the q/Q wrapper streams.
    first = contents.get_object(0)
    last = contents.get_object(2)
    assert isinstance(first, COSStream)
    assert isinstance(last, COSStream)
    assert first.get_raw_data().strip() == b"q"
    assert last.get_raw_data().strip() == b"Q"
    doc.close()


def test_wrap_in_save_restore_extends_existing_array() -> None:
    """Existing array /Contents grows by 2 (q at front, Q at back)."""
    doc = PDDocument()
    page = PDPage()
    arr = COSArray()
    s1 = COSStream()
    s1.set_raw_data(b"x")
    s2 = COSStream()
    s2.set_raw_data(b"y")
    arr.add(s1)
    arr.add(s2)
    page.get_cos_object().set_item(COSName.CONTENTS, arr)
    doc.add_page(page)

    util = LayerUtility(doc)
    util.wrap_in_save_restore(page)
    contents = page.get_cos_object().get_dictionary_object(COSName.CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 4
    assert contents.get_object(0).get_raw_data().strip() == b"q"
    assert contents.get_object(3).get_raw_data().strip() == b"Q"
    doc.close()


# ---------- import_page_as_form ----------


def test_import_page_as_form_returns_form_xobject_with_resources_and_bbox() -> None:
    src = _make_doc_with_one_page()
    target = PDDocument()
    target.add_page(PDPage())
    util = LayerUtility(target)
    form = util.import_page_as_form(src, 0)

    # /Subtype /Form on the form's COS dict.
    cos = form.get_cos_object()
    assert cos.get_name(COSName.SUBTYPE) == "Form"
    # /BBox copied from the source page's media/crop box.
    bbox = form.get_b_box()
    assert bbox is not None
    src_media = src.get_page(0).get_media_box()
    assert bbox.get_lower_left_x() == src_media.get_lower_left_x()
    assert bbox.get_upper_right_x() == src_media.get_upper_right_x()
    # /Resources is set (deep-cloned, so a *new* dict, not the source's).
    res = form.get_resources()
    assert res is not None
    assert res.get_cos_object() is not src.get_page(0).get_resources().get_cos_object()
    src.close()
    target.close()


def test_import_page_as_form_accepts_pdpage_argument() -> None:
    """Upstream's two overloads — int or PDPage — both work."""
    src = _make_doc_with_one_page()
    target = PDDocument()
    target.add_page(PDPage())
    util = LayerUtility(target)
    form = util.import_page_as_form(src, src.get_page(0))
    assert form.get_cos_object().get_name(COSName.SUBTYPE) == "Form"
    src.close()
    target.close()


# ---------- append_form_as_layer ----------


def test_append_form_as_layer_creates_ocg_in_catalog_and_page_resources() -> None:
    """Hand-written: add a layer and verify catalog /OCProperties/OCGs and
    the page's /Resources/Properties slot reference the new OCG."""
    src = _make_doc_with_one_page()
    target = _make_doc_with_one_page()

    util = LayerUtility(target)
    form = util.import_page_as_form(src, 0)
    target_page = target.get_page(0)
    layer = util.append_form_as_layer(target_page, form, None, "overlay")

    # The returned layer is a real PDOptionalContentGroup.
    assert isinstance(layer, PDOptionalContentGroup)
    assert layer.get_name() == "overlay"

    # Catalog now has /OCProperties referencing the layer.
    catalog = target.get_document_catalog()
    oc_props = catalog.get_oc_properties()
    assert isinstance(oc_props, PDOptionalContentProperties)
    assert oc_props.has_group("overlay")
    fetched = oc_props.get_group("overlay")
    assert fetched is not None
    assert fetched.get_name() == "overlay"
    # The OCG dict in /OCGs is the SAME dict as the layer we returned.
    assert fetched.get_cos_object() is layer.get_cos_object()

    # Page resources have a /Properties slot pointing at our OCG.
    res_dict = target_page.get_resources().get_cos_object()
    props = res_dict.get_dictionary_object(COSName.get_pdf_name("Properties"))
    assert isinstance(props, COSDictionary)
    referenced = [
        props.get_dictionary_object(k) for k in props.key_set()
    ]
    assert layer.get_cos_object() in referenced

    src.close()
    target.close()


def test_append_form_as_layer_rejects_duplicate_layer_name() -> None:
    src = _make_doc_with_one_page()
    target = _make_doc_with_one_page()
    util = LayerUtility(target)
    form = util.import_page_as_form(src, 0)
    target_page = target.get_page(0)
    util.append_form_as_layer(target_page, form, None, "overlay")
    with pytest.raises(ValueError):
        util.append_form_as_layer(target_page, form, None, "overlay")
    src.close()
    target.close()


def test_append_form_as_layer_emits_oc_marked_content_in_page_stream() -> None:
    """The new content stream contains ``/OC /<key> BDC ... EMC`` so a
    consumer can recognise the layer marker and ``Do`` opcode for the form."""
    src = _make_doc_with_one_page()
    target = _make_doc_with_one_page()
    util = LayerUtility(target)
    form = util.import_page_as_form(src, 0)
    target_page = target.get_page(0)
    util.append_form_as_layer(target_page, form, None, "overlay")
    body = target_page.get_contents()
    assert b"/OC" in body
    assert b"BDC" in body
    assert b"EMC" in body
    assert b"Do" in body
    src.close()
    target.close()


def test_get_document_returns_target_document() -> None:
    target = _make_doc_with_one_page()
    util = LayerUtility(target)
    assert util.get_document() is target
    target.close()


# ---------- create_overlay_x_object / name_already_used ----------


def test_create_overlay_x_object_auto_allocates_form_key() -> None:
    """Default path delegates to PDResources.add_x_object → ``Form0``."""
    src = _make_doc_with_one_page()
    target = _make_doc_with_one_page()
    util = LayerUtility(target)
    form = util.import_page_as_form(src, 0)
    target_page = target.get_page(0)
    name = util.create_overlay_x_object(target_page, form)
    assert name.get_name() == "Form0"
    # Calling again allocates the next free slot.
    form2 = util.import_page_as_form(src, 0)
    name2 = util.create_overlay_x_object(target_page, form2)
    assert name2.get_name() == "Form1"
    src.close()
    target.close()


def test_create_overlay_x_object_honors_desired_name() -> None:
    src = _make_doc_with_one_page()
    target = _make_doc_with_one_page()
    util = LayerUtility(target)
    form = util.import_page_as_form(src, 0)
    target_page = target.get_page(0)
    name = util.create_overlay_x_object(target_page, form, desired_name="MyOverlay")
    assert name.get_name() == "MyOverlay"
    assert util.name_already_used(target_page, "MyOverlay") is True
    src.close()
    target.close()


def test_create_overlay_x_object_rejects_duplicate_desired_name() -> None:
    src = _make_doc_with_one_page()
    target = _make_doc_with_one_page()
    util = LayerUtility(target)
    form = util.import_page_as_form(src, 0)
    target_page = target.get_page(0)
    util.create_overlay_x_object(target_page, form, desired_name="MyOverlay")
    form2 = util.import_page_as_form(src, 0)
    with pytest.raises(ValueError):
        util.create_overlay_x_object(target_page, form2, desired_name="MyOverlay")
    src.close()
    target.close()


def test_name_already_used_returns_false_when_unset() -> None:
    target = _make_doc_with_one_page()
    util = LayerUtility(target)
    target_page = target.get_page(0)
    assert util.name_already_used(target_page, "Form0") is False
    target.close()
