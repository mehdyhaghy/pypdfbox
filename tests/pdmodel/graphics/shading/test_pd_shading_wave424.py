from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSObject, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType2
from pypdfbox.pdmodel.graphics.shading import PDShading


class _ConcreteShading(PDShading):
    def __init__(
        self,
        dictionary_or_stream: COSDictionary | None = None,
        shading_type: int = PDShading.SHADING_TYPE2,
    ) -> None:
        super().__init__(dictionary_or_stream)
        self._shading_type = shading_type

    def get_shading_type(self) -> int:
        return self._shading_type


def _numbers(*values: float) -> COSArray:
    return COSArray([COSFloat(v) for v in values])


def _type2_function(c0: float, c1: float) -> PDFunctionType2:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunctionType2(raw)
    fn.set_c0([c0])
    fn.set_c1([c1])
    fn.set_n(1.0)
    return fn


def test_constructor_accepts_stream_because_stream_is_a_dictionary() -> None:
    stream = COSStream()
    shading = _ConcreteShading(stream)

    assert shading.get_cos_object() is stream
    assert shading.get_type() == "Shading"


def test_constructor_rejects_non_dictionary() -> None:
    with pytest.raises(TypeError, match="PDShading expects COSDictionary"):
        _ConcreteShading(COSName.get_pdf_name("NotADictionary"))  # type: ignore[arg-type]


def test_base_get_shading_type_is_abstract() -> None:
    with pytest.raises(NotImplementedError, match="PDShading is abstract"):
        PDShading().get_shading_type()


def test_create_returns_none_and_rejects_non_dictionary() -> None:
    assert PDShading.create(None) is None
    with pytest.raises(TypeError, match="PDShading.create expects COSDictionary"):
        PDShading.create(COSName.get_pdf_name("Bad"))  # type: ignore[arg-type]


def test_create_rejects_missing_or_invalid_shading_type() -> None:
    # Upstream getInt(SHADING_TYPE, 0) → missing /ShadingType defaults to 0,
    # which falls through the switch to "Error: Unknown shading type 0"
    # (retargeted in wave 1513 from the old -1 sentinel + "Invalid ShadingType"
    # wording, both non-upstream; caught by the ShadingPatternFuzzProbe oracle).
    with pytest.raises(OSError, match="Error: Unknown shading type 0"):
        PDShading.create(COSDictionary())

    raw = COSDictionary()
    raw.set_int("ShadingType", 99)
    with pytest.raises(OSError, match="Error: Unknown shading type 99"):
        PDShading.create(raw)


def test_set_shading_type_writes_backing_dictionary() -> None:
    shading = _ConcreteShading()
    shading.set_shading_type(PDShading.SHADING_TYPE3)

    assert shading.get_cos_object().get_int("ShadingType") == 3


def test_raw_color_space_accessors_prefer_color_space_and_clear_both_keys() -> None:
    shading = _ConcreteShading()
    shading.get_cos_object().set_item("CS", COSName.get_pdf_name("DeviceGray"))
    assert shading.has_color_space() is True
    assert shading.get_color_space() is COSName.get_pdf_name("DeviceGray")

    rgb = COSName.get_pdf_name("DeviceRGB")
    shading.set_color_space(rgb)
    assert shading.get_color_space() is rgb

    shading.set_color_space(None)
    assert shading.has_color_space() is False
    assert shading.get_cos_object().get_dictionary_object("ColorSpace") is None
    assert shading.get_cos_object().get_dictionary_object("CS") is None


def test_background_accessors_ignore_malformed_entries_and_clear_valid_entry() -> None:
    shading = _ConcreteShading()
    shading.get_cos_object().set_item("Background", COSName.get_pdf_name("Bad"))
    assert shading.get_background() is None
    assert shading.has_background() is False

    empty = COSArray()
    shading.set_background(empty)
    assert shading.get_background() is empty
    assert shading.has_background() is False

    values = _numbers(0.1, 0.2, 0.3)
    shading.set_background(values)
    assert shading.has_background() is True
    shading.set_background(None)
    assert shading.get_background() is None


def test_b_box_accessors_require_numeric_four_array_for_presence() -> None:
    shading = _ConcreteShading()
    short = _numbers(0.0, 0.0, 10.0)
    shading.set_b_box(short)
    assert shading.get_b_box() is short
    assert shading.has_b_box() is False

    malformed = COSArray([COSFloat(0.0), COSFloat(0.0), COSName.get_pdf_name("Bad"), COSFloat(1.0)])
    shading.set_b_box(malformed)
    assert shading.has_b_box() is False

    valid = _numbers(0.0, 0.0, 10.0, 20.0)
    shading.set_b_box(valid)
    assert shading.has_b_box() is True
    shading.clear_b_box()
    assert shading.get_b_box() is None


def test_anti_alias_presence_tracks_only_cos_boolean_values() -> None:
    shading = _ConcreteShading()
    assert shading.has_anti_alias() is False
    assert shading.get_anti_alias() is False

    shading.set_anti_alias(True)
    assert shading.has_anti_alias() is True
    assert shading.is_anti_alias() is True

    shading.get_cos_object().set_item("AntiAlias", COSName.get_pdf_name("Yes"))
    assert shading.has_anti_alias() is False
    assert shading.get_anti_alias() is False

    shading.clear_anti_alias()
    assert shading.has_anti_alias() is False


def test_get_function_returns_raw_array_and_get_functions_array_skips_null_refs() -> None:
    shading = _ConcreteShading()
    first = _type2_function(0.0, 1.0).get_cos_object()
    functions = COSArray([first, COSObject(424, 0)])
    shading.set_function(functions)

    assert shading.get_function() is functions
    wrapped = shading.get_functions_array()
    assert len(wrapped) == 1
    assert isinstance(wrapped[0], PDFunctionType2)


def test_set_function_accepts_function_objects_raw_cos_and_iterables() -> None:
    shading = _ConcreteShading()
    first = _type2_function(0.0, 1.0)
    second = _type2_function(1.0, 0.0)

    shading.set_function(first)
    assert shading.get_cos_object().get_dictionary_object("Function") is first.get_cos_object()

    raw = COSStream()
    raw.set_int("FunctionType", 4)
    shading.set_function(raw)
    assert shading.get_cos_object().get_dictionary_object("Function") is raw

    shading.set_function([first, second.get_cos_object()])
    stored = shading.get_cos_object().get_dictionary_object("Function")
    assert isinstance(stored, COSArray)
    assert stored.size() == 2

    shading.clear_function()
    assert shading.has_function() is False


def test_set_function_rejects_non_iterable_and_bad_iterable_entries() -> None:
    shading = _ConcreteShading()

    with pytest.raises(TypeError, match="set_function expects"):
        shading.set_function(42)

    with pytest.raises(TypeError, match="iterable entries"):
        shading.set_function([object()])


def test_eval_function_requires_function_and_clamps_single_function_outputs() -> None:
    shading = _ConcreteShading()
    with pytest.raises(OSError, match="mandatory /Function"):
        shading.eval_function(0.5)

    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunctionType2(raw)
    fn.set_c0([-1.0, 0.25])
    fn.set_c1([2.0, 1.5])
    fn.set_n(1.0)
    shading.set_function(fn)

    assert shading.eval_function(1.0) == [1.0, 1.0]


def test_eval_function_with_multiple_functions_uses_first_output_from_each() -> None:
    shading = _ConcreteShading()
    shading.set_function([_type2_function(-2.0, -1.0), _type2_function(2.0, 3.0)])

    assert shading.eval_function([1.0]) == [0.0, 1.0]


def test_has_function_accepts_dictionary_stream_or_array_only() -> None:
    shading = _ConcreteShading()
    shading.get_cos_object().set_item("Function", COSName.get_pdf_name("Identity"))
    assert shading.has_function() is False

    shading.set_function(COSArray())
    assert shading.has_function() is True


def test_get_bounds_default_ignores_arguments() -> None:
    assert _ConcreteShading().get_bounds(object(), object()) is None
