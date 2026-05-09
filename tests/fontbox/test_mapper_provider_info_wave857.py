from __future__ import annotations

import types

import pytest

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_provider import FontProvider

from . import test_font_info as font_info_tests
from . import test_font_provider as font_provider_tests


def _local_class_code(function: object, name: str) -> types.CodeType:
    code = function.__code__  # type: ignore[attr-defined]
    for const in code.co_consts:
        if isinstance(const, types.CodeType) and const.co_name == name:
            return const
    raise AssertionError(f"{name} not found in {function!r}")


def _class_namespace(code: types.CodeType, module_name: str) -> dict[str, object]:
    namespace: dict[str, object] = {}
    exec(code, {"__name__": module_name}, namespace)
    return namespace


def test_wave857_font_info_stub_font_exercises_protocol_methods() -> None:
    font = font_info_tests._StubFont()

    assert font.get_name() == "StubFont"
    assert font.get_font_bbox() == (0, 0, 0, 0)
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert font.get_path("A") == []
    assert font.get_width("A") == 0.0
    assert font.has_glyph("A") is False


def test_wave857_font_info_stub_info_materializes_font_and_panose() -> None:
    panose = object()
    info = font_info_tests._StubFontInfo(panose=panose)

    assert isinstance(info.get_font(), font_info_tests._StubFont)
    assert info.get_panose() is panose


def test_wave857_font_provider_stub_info_exercises_all_accessors() -> None:
    info = font_provider_tests._StubInfo("WaveProviderFont")

    assert info.get_post_script_name() == "WaveProviderFont"
    assert info.get_format() is FontFormat.TTF
    assert info.get_cid_system_info() is None
    with pytest.raises(NotImplementedError):
        info.get_font()
    assert info.get_family_class() == -1
    assert info.get_weight_class() == -1
    assert info.get_code_page_range1() == 0
    assert info.get_code_page_range2() == 0
    assert info.get_mac_style() == -1
    assert info.get_panose() is None


def test_wave857_font_provider_local_only_debug_method_body_runs() -> None:
    code = _local_class_code(font_provider_tests.test_partial_subclass_still_abstract, "_OnlyDebug")
    namespace = _class_namespace(code, font_provider_tests.__name__)
    only_debug = type(
        "_OnlyDebug",
        (FontProvider,),
        {k: v for k, v in namespace.items() if not k.startswith("__")},
    )

    assert only_debug.to_debug_string(object()) is None


def test_wave857_local_class_lookup_reports_missing_helper() -> None:
    with pytest.raises(AssertionError, match="Missing"):
        _local_class_code(font_provider_tests.test_partial_subclass_still_abstract, "Missing")
