from __future__ import annotations

import builtins

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


def _dash(values: list[float]) -> COSArray:
    array = COSArray()
    array.set_float_array(values)
    return array


def test_line_dash_tail_branches_for_phase_cos_and_debug_helpers() -> None:
    pattern = PDLineDashPattern(_dash([3.0, 5.0]), -40)
    assert pattern.get_phase() == 8

    with pytest.raises(TypeError):
        PDLineDashPattern.from_cos_array("not an array")  # type: ignore[arg-type]

    serialized = COSArray()
    serialized.add(_dash([2.0]))
    serialized.add(COSName.get_pdf_name("BadPhase"))
    from_bad_phase = PDLineDashPattern.from_cos_array(serialized)
    assert from_bad_phase.get_phase() == 0

    assert PDLineDashPattern().is_zero_pattern() is False
    assert repr(from_bad_phase) == "PDLineDashPattern(array=[2.0], phase=0)"
    assert from_bad_phase.__eq__(object()) is NotImplemented


def test_soft_mask_get_group_propagates_import_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = COSStream()
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("G"), stream)
    mask = PDSoftMask(raw)
    original_import = builtins.__import__

    def blocked_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "pypdfbox.pdmodel.graphics.form.pd_form_x_object":
            raise ImportError("blocked for branch coverage")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(ImportError, match="blocked for branch coverage"):
        mask.get_group()


def test_soft_mask_get_group_rejects_invalid_xobject_subtype() -> None:
    stream = COSStream()
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Bogus"))  # type: ignore[attr-defined]
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("G"), stream)
    mask = PDSoftMask(raw)

    with pytest.raises(OSError, match="Invalid XObject Subtype: Bogus"):
        mask.get_group()


def test_soft_mask_get_group_propagates_unexpected_factory_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = COSStream()
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Form"))  # type: ignore[attr-defined]
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("G"), stream)
    mask = PDSoftMask(raw)

    def boom(base: object, resources: object = None) -> object:
        raise RuntimeError("factory failure")

    monkeypatch.setattr(PDXObject, "create_x_object", staticmethod(boom))

    with pytest.raises(RuntimeError, match="factory failure"):
        mask.get_group()


def test_tiling_pattern_tail_clear_and_non_stream_content_error() -> None:
    pattern = PDTilingPattern()
    pattern.set_b_box(PDRectangle.from_width_height(10, 20))
    assert pattern.has_b_box() is True
    pattern.clear_b_box()
    assert pattern.has_b_box() is False

    plain = COSDictionary()
    degenerate = PDTilingPattern.__new__(PDTilingPattern)
    degenerate._dict = plain  # type: ignore[attr-defined]
    degenerate._resource_cache = None  # type: ignore[attr-defined]

    with pytest.raises(TypeError, match="not backed by a COSStream"):
        degenerate.get_content_stream()


def test_tiling_pattern_set_resources_none_clears_entry() -> None:
    pattern = PDTilingPattern()
    assert pattern.has_resources() is True

    pattern.set_resources(None)

    assert pattern.has_resources() is False
    assert pattern.get_resources() is None


def test_tiling_pattern_set_resources_rejects_non_dictionary() -> None:
    pattern = PDTilingPattern()

    with pytest.raises(TypeError):
        pattern.set_resources(COSName.get_pdf_name("Resources"))  # type: ignore[arg-type]


def test_tiling_pattern_round_trips_raw_resources_dict() -> None:
    pattern = PDTilingPattern()
    resources = COSDictionary()
    resources.set_item(COSName.get_pdf_name("Marker"), COSInteger.get(1))

    pattern.set_resources(resources)

    got = pattern.get_resources()
    assert isinstance(got, PDResources)
    assert got.get_cos_object() is resources
