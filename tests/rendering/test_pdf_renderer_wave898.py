from __future__ import annotations

import types

import pytest

from pypdfbox.cos import COSName

from . import test_pdf_renderer_wave701 as wave701


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


def test_wave898_wave701_make_doc_and_rgb_function_success_path() -> None:
    doc, page = wave701._make_doc(8.0, 9.0)
    try:
        assert doc.get_number_of_pages() == 1
        assert page.get_media_box().width == 8.0
        assert page.get_media_box().height == 9.0
    finally:
        doc.close()

    function = wave701._RGBFunction([0.1, 0.2, 0.3])
    assert function.eval([0.5]) == [0.1, 0.2, 0.3]


def test_wave898_wave701_local_axial_color_space_helper_runs() -> None:
    axial_cls = _local_class(
        wave701.test_axial_shading_uses_black_ramp_entry_when_eval_fails,
        "_Axial",
        wave701.__dict__,
    )
    axial = axial_cls()

    color_space = axial.get_color_space()

    assert isinstance(color_space, COSName)
    assert color_space.get_name() == "DeviceRGB"


def test_wave898_local_class_lookup_reports_missing_helper() -> None:
    with pytest.raises(AssertionError, match="_Missing"):
        _local_class(
            wave701.test_axial_shading_uses_black_ramp_entry_when_eval_fails,
            "_Missing",
            wave701.__dict__,
        )

