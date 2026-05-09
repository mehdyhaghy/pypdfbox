from __future__ import annotations

import types

import pytest

from . import test_pdf_renderer_wave681 as wave681
from . import test_pdf_renderer_wave691 as wave691


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


def test_wave897_wave681_make_doc_and_box_origin_helpers() -> None:
    doc, page = wave681._make_doc(2.0, 5.0)
    try:
        assert doc.get_number_of_pages() == 1
        assert page.get_media_box().width == 2.0
        assert page.get_media_box().height == 5.0
    finally:
        doc.close()

    box = wave681._Box(width=3.0, height=4.0)
    assert box.get_width() == 3.0
    assert box.get_height() == 4.0
    assert box.get_lower_left_x() == 0.0
    assert box.get_lower_left_y() == 0.0


def test_wave897_wave691_make_doc_and_local_pattern_helpers() -> None:
    doc, page = wave691._make_doc(6.0, 7.0)
    try:
        assert doc.get_number_of_pages() == 1
        assert page.get_media_box().width == 6.0
        assert page.get_media_box().height == 7.0
    finally:
        doc.close()

    pattern_cls = _local_class(
        wave691.test_shading_and_tiling_noops_preserve_canvas,
        "_Pattern",
        wave691.__dict__,
    )
    pattern = pattern_cls()

    assert isinstance(pattern.get_b_box(), wave691._Box)
    assert pattern.get_x_step() == 1.0
    assert pattern.get_y_step() == 1.0


def test_wave897_local_class_lookup_reports_missing_helper() -> None:
    with pytest.raises(AssertionError, match="_Missing"):
        _local_class(
            wave691.test_shading_and_tiling_noops_preserve_canvas,
            "_Missing",
            wave691.__dict__,
        )

