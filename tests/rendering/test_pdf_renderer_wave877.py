from __future__ import annotations

import types

import pytest

from pypdfbox.cos import COSStream

from . import test_pdf_renderer_wave512 as wave512


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


def test_wave877_make_doc_removes_initial_page_and_returns_requested_size() -> None:
    doc, page = wave512._make_doc(3.0, 4.0)
    try:
        assert doc.get_number_of_pages() == 1
        assert page.get_media_box().width == 3.0
        assert page.get_media_box().height == 4.0
    finally:
        doc.close()


def test_wave877_tiling_bbox_and_pattern_local_helpers_run() -> None:
    bbox_cls = _local_class(
        wave512.test_render_tiling_cell_restores_resources_when_pattern_has_none,
        "_BBox",
        wave512.__dict__,
    )
    pattern_cls = _local_class(
        wave512.test_render_tiling_cell_restores_resources_when_pattern_has_none,
        "_Pattern",
        wave512.__dict__,
    )

    bbox = bbox_cls()
    pattern = pattern_cls()

    assert bbox.get_width() == 1.0
    assert bbox.get_height() == 1.0
    assert bbox.get_lower_left_x() == 0.0
    assert bbox.get_lower_left_y() == 0.0
    assert isinstance(pattern.get_cos_object(), COSStream)
    assert pattern.get_resources() is None


def test_wave877_local_class_lookup_reports_missing_helper() -> None:
    with pytest.raises(AssertionError, match="_Missing"):
        _local_class(
            wave512.test_render_tiling_cell_restores_resources_when_pattern_has_none,
            "_Missing",
            wave512.__dict__,
        )

