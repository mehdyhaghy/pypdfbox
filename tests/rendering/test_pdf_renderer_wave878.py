from __future__ import annotations

import types

import pytest

from pypdfbox.cos import COSDictionary, COSName

from . import test_pdf_renderer_wave542 as wave542
from . import test_pdf_renderer_wave581 as wave581


def _local_class(function: object, name: str, module_globals: dict[str, object]) -> type:
    code = function.__code__  # type: ignore[attr-defined]
    for const in code.co_consts:
        if isinstance(const, types.CodeType) and const.co_name == name:
            namespace: dict[str, object] = {}
            exec(const, module_globals, namespace)
            return type(
                name,
                (),
                {
                    k: v
                    for k, v in namespace.items()
                    if k == "__init__" or not k.startswith("__")
                },
            )
    raise AssertionError(f"{name} not found")


def test_wave878_wave542_make_doc_and_finish_flush_live_draw() -> None:
    doc, page = wave542._make_doc(2.0, 3.0)
    try:
        assert doc.get_number_of_pages() == 1
        assert page.get_media_box().width == 2.0
        assert page.get_media_box().height == 3.0
    finally:
        doc.close()

    prepared_doc, renderer = wave542._prepared_renderer((2, 2))
    try:
        assert renderer._draw is not None  # noqa: SLF001
        wave542._finish(renderer)
    finally:
        prepared_doc.close()


def test_wave878_wave542_form_get_group_builds_transparency_dictionary() -> None:
    form_cls = _local_class(
        wave542.test_transparency_group_helper_result_takes_precedence_over_group_dict,
        "_Form",
        wave542.__dict__,
    )
    form = form_cls()

    group = form.get_group()

    assert isinstance(group, COSDictionary)
    assert group.get_name(COSName.get_pdf_name("S")) == "Transparency"


def test_wave878_wave581_make_doc_and_image_xobject_helpers_run() -> None:
    doc, page = wave581._make_doc(5.0, 6.0)
    try:
        assert doc.get_number_of_pages() == 1
        assert page.get_media_box().width == 5.0
        assert page.get_media_box().height == 6.0
    finally:
        doc.close()

    image_cls = _local_class(
        wave581.test_decode_image_xobject_rejects_invalid_raw_image_shapes,
        "_ImageXObject",
        wave581.__dict__,
    )
    image = image_cls(width=7, height=8, bpc=1, color_space=COSName.get_pdf_name("DeviceGray"))

    assert isinstance(image.get_cos_object(), COSDictionary)
    assert image.get_width() == 7
    assert image.get_height() == 8
    assert image.get_bits_per_component() == 1
    assert image.get_color_space().get_name() == "DeviceGray"


def test_wave878_local_class_lookup_reports_missing_helper() -> None:
    with pytest.raises(AssertionError, match="_Missing"):
        _local_class(
            wave581.test_decode_image_xobject_rejects_invalid_raw_image_shapes,
            "_Missing",
            wave581.__dict__,
        )

