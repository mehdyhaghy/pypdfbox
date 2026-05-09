from __future__ import annotations

import types

import pytest

from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_mapper import FontMapper

from . import test_font_mapper as font_mapper_tests
from . import test_font_mappers as font_mappers_tests


def _cell(value: object) -> object:
    return (lambda: value).__closure__[0]  # type: ignore[index]


def _local_class_code(function: object, name: str) -> types.CodeType:
    code = function.__code__  # type: ignore[attr-defined]
    for const in code.co_consts:
        if isinstance(const, types.CodeType) and const.co_name == name:
            return const
    raise AssertionError(f"{name} not found in {function!r}")


def _namespace_from_local_class(
    function: object,
    name: str,
    module_name: str,
    closure: tuple[object, ...] | None = None,
) -> dict[str, object]:
    namespace: dict[str, object] = {}
    code = _local_class_code(function, name)
    if closure is None:
        exec(code, {"__name__": module_name}, namespace)
    else:
        exec(code, {"__name__": module_name}, namespace, closure=closure)
    return namespace


def _mapper_from_local_class(
    function: object,
    name: str,
    closure: tuple[object, ...] | None = None,
) -> FontMapper:
    namespace = _namespace_from_local_class(
        function,
        name,
        font_mapper_tests.__name__,
        closure,
    )
    cls = type(
        name,
        (FontMapper,),
        {k: v for k, v in namespace.items() if not k.startswith("__")},
    )
    return cls()  # type: ignore[abstract]


def test_wave858_font_mapper_partial_font_get_name_body_runs() -> None:
    namespace = _namespace_from_local_class(
        font_mapper_tests.test_protocol_rejects_non_font_objects,
        "_PartialFont",
        font_mapper_tests.__name__,
    )
    partial_font = type(
        "_PartialFont",
        (),
        {k: v for k, v in namespace.items() if not k.startswith("__")},
    )()

    assert partial_font.get_name() == "x"


def test_wave858_font_mapper_abstract_half_method_body_runs_unbound() -> None:
    namespace = _namespace_from_local_class(
        font_mapper_tests.test_subclass_must_implement_all_three_methods,
        "_Half",
        font_mapper_tests.__name__,
    )
    half = type(
        "_Half",
        (FontMapper,),
        {k: v for k, v in namespace.items() if not k.startswith("__")},
    )

    assert half.get_true_type_font(object(), "Base", None) is None


def test_wave858_font_mapper_no_cid_stub_methods_return_none() -> None:
    mapper = _mapper_from_local_class(
        font_mapper_tests.test_get_cid_font_is_concrete_with_default_none,
        "_NoCID",
    )

    assert mapper.get_true_type_font("Base", None) is None
    assert mapper.get_open_type_font("Base", None) is None
    assert mapper.get_font_box_font("Base", None) is None


def test_wave858_font_mapper_cid_override_stub_methods_return_none() -> None:
    mapper = _mapper_from_local_class(
        font_mapper_tests.test_subclasses_can_override_get_cid_font,
        "_CIDMapper",
        closure=(_cell(CIDFontMapping), _cell([])),
    )

    assert mapper.get_true_type_font("Base", None) is None
    assert mapper.get_open_type_font("Base", None) is None
    assert mapper.get_font_box_font("Base", None) is None


def test_wave858_font_mappers_local_stub_methods_return_none() -> None:
    functions = [
        font_mappers_tests.test_set_swaps_the_active_mapper,
        font_mappers_tests.test_set_none_resets_to_default,
        font_mappers_tests.test_reset_clears_override,
        font_mappers_tests.test_set_mapper_camelcase_alias_works,
    ]

    for function in functions:
        namespace = _namespace_from_local_class(function, "_Stub", font_mappers_tests.__name__)
        cls = type(
            "_Stub",
            (FontMapper,),
            {k: v for k, v in namespace.items() if not k.startswith("__")},
        )
        mapper = cls()
        assert mapper.get_true_type_font("Base", None) is None
        assert mapper.get_open_type_font("Base", None) is None
        assert mapper.get_font_box_font("Base", None) is None


def test_wave858_local_class_lookup_reports_missing_helper() -> None:
    with pytest.raises(AssertionError, match="Missing"):
        _local_class_code(font_mapper_tests.test_protocol_rejects_non_font_objects, "Missing")
