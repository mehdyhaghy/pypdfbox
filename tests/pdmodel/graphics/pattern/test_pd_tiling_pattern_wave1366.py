"""Deep parity tests for ``PDTilingPattern``. Complements
``test_pattern_parity.py`` with focused coverage of ``/Resources`` typed
accessors, ``/BBox`` typed round-trip via ``PDRectangle``, and the
``PDContentStream`` surface (``get_contents`` /
``get_contents_for_random_access`` / ``get_contents_for_stream_parsing``).

Mirrors upstream
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/pattern/PDTilingPattern.java``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.graphics.pattern import (
    PDAbstractPattern,
    PDTilingPattern,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


def test_fresh_tiling_pattern_writes_type_and_pattern_type():
    pattern = PDTilingPattern()
    cos = pattern.get_cos_object()
    # Spec: /Type /Pattern + /PatternType 1.
    assert cos.get_name(COSName.TYPE) == "Pattern"
    assert cos.get_int("PatternType") == PDAbstractPattern.TYPE_TILING_PATTERN
    # Spec: stream-backed (carries a content stream describing one tile).
    assert isinstance(cos, COSStream)


def test_fresh_tiling_pattern_has_default_empty_resources():
    pattern = PDTilingPattern()
    resources = pattern.get_resources()
    assert resources is not None
    assert isinstance(resources, PDResources)
    # Default resources dict has no entries.
    assert resources.get_cos_object().size() == 0


def test_set_resources_accepts_pd_resources_instance():
    pattern = PDTilingPattern()
    fresh = PDResources()
    pattern.set_resources(fresh)
    got = pattern.get_resources()
    assert got is not None
    assert got.get_cos_object() is fresh.get_cos_object()


def test_set_resources_accepts_raw_cos_dictionary():
    pattern = PDTilingPattern()
    raw = COSDictionary()
    pattern.set_resources(raw)
    got = pattern.get_resources()
    assert got is not None
    assert got.get_cos_object() is raw


def test_set_resources_with_none_clears_entry():
    pattern = PDTilingPattern()
    pattern.set_resources(None)
    assert pattern.get_resources() is None
    assert pattern.has_resources() is False


def test_set_resources_rejects_non_resources_non_dictionary():
    pattern = PDTilingPattern()
    with pytest.raises(TypeError):
        pattern.set_resources(42)  # type: ignore[arg-type]


def test_has_resources_reflects_presence():
    pattern = PDTilingPattern()
    assert pattern.has_resources() is True  # default ctor attaches resources
    pattern.clear_resources()
    assert pattern.has_resources() is False


def test_clear_resources_is_noop_when_absent():
    pattern = PDTilingPattern()
    pattern.clear_resources()
    pattern.clear_resources()  # double-clear must not raise
    assert pattern.get_resources() is None


# ---------------------------------------------------------------------------
# /BBox typed round-trip
# ---------------------------------------------------------------------------


def test_set_b_box_accepts_pd_rectangle():
    pattern = PDTilingPattern()
    rect = PDRectangle(10.0, 20.0, 200.0, 300.0)
    pattern.set_b_box(rect)
    got = pattern.get_b_box()
    assert got is not None
    assert isinstance(got, PDRectangle)
    assert got.get_lower_left_x() == pytest.approx(10.0)
    assert got.get_lower_left_y() == pytest.approx(20.0)


def test_set_b_box_accepts_cos_array():
    pattern = PDTilingPattern()
    arr = COSArray()
    for v in (0.0, 0.0, 100.0, 100.0):
        arr.add(COSFloat(v))
    pattern.set_b_box(arr)
    # Identity preserved.
    assert pattern.get_cos_object().get_dictionary_object("BBox") is arr


def test_set_b_box_rejects_unsupported_type():
    pattern = PDTilingPattern()
    with pytest.raises(TypeError):
        pattern.set_b_box(42)  # type: ignore[arg-type]


def test_get_b_box_coerces_non_numeric_entries_in_four_entry_array():
    # A 4-entry /BBox passes get_b_box's own length guard; upstream
    # ``new PDRectangle(COSArray)`` coerces the non-numeric slot to 0.0 and
    # normalizes, so ``[0, /Bogus, 100, 100]`` yields a real rectangle and
    # has_b_box() is True.
    pattern = PDTilingPattern()
    arr = COSArray()
    arr.add(COSFloat(0.0))
    arr.add(COSName.get_pdf_name("Bogus"))
    arr.add(COSFloat(100.0))
    arr.add(COSFloat(100.0))
    pattern.get_cos_object().set_item(COSName.get_pdf_name("BBox"), arr)
    assert pattern.get_b_box() == PDRectangle(0.0, 0.0, 100.0, 100.0)
    assert pattern.has_b_box() is True


# ---------------------------------------------------------------------------
# /XStep, /YStep round-trip + default
# ---------------------------------------------------------------------------


def test_x_step_y_step_default_is_zero():
    pattern = PDTilingPattern()
    assert pattern.get_x_step() == 0.0
    assert pattern.get_y_step() == 0.0


def test_x_step_y_step_negative_values_allowed():
    # PDF spec forbids zero (would cause an infinite tile loop) but the
    # wrapper itself is permissive — caller validation belongs to the
    # writer / sanitizer.
    pattern = PDTilingPattern()
    pattern.set_x_step(-10.0)
    pattern.set_y_step(-20.0)
    assert pattern.get_x_step() == pytest.approx(-10.0)
    assert pattern.get_y_step() == pytest.approx(-20.0)


def test_x_step_y_step_round_trip_integer_setter_via_dict():
    # If a parser writes /XStep as a COSInteger, the float getter must still
    # return the value as a float without losing precision.
    pattern = PDTilingPattern()
    pattern.get_cos_object().set_item(
        COSName.get_pdf_name("XStep"), COSInteger.get(72)
    )
    assert pattern.get_x_step() == pytest.approx(72.0)


# ---------------------------------------------------------------------------
# PDContentStream surface
# ---------------------------------------------------------------------------


def _write_empty_body(pattern: PDTilingPattern) -> None:
    """Allocate a zero-byte body so the COSStream's ``create_input_stream`` /
    ``create_raw_input_stream`` paths have something to return. Fresh streams
    raise ``OSError('stream has no data')`` otherwise."""
    cos = pattern.get_cos_object()
    assert isinstance(cos, COSStream)
    with cos.create_output_stream() as out:
        out.write(b"")


def test_get_contents_returns_decoded_input_stream():
    pattern = PDTilingPattern()
    _write_empty_body(pattern)
    contents = pattern.get_contents()
    assert contents is not None
    # Empty content stream — reading should yield zero bytes.
    assert contents.read() == b""


def test_get_contents_for_random_access_returns_raw_stream():
    pattern = PDTilingPattern()
    _write_empty_body(pattern)
    raw = pattern.get_contents_for_random_access()
    assert raw is not None
    # Random-access view is seekable.
    assert hasattr(raw, "seek")
    assert hasattr(raw, "read")


def test_get_contents_for_stream_parsing_delegates_to_random_access():
    pattern = PDTilingPattern()
    _write_empty_body(pattern)
    parsing = pattern.get_contents_for_stream_parsing()
    random_access = pattern.get_contents_for_random_access()
    assert parsing is not None
    assert random_access is not None


def test_get_content_stream_returns_pd_stream():
    from pypdfbox.pdmodel.common.pd_stream import PDStream

    pattern = PDTilingPattern()
    pd_stream = pattern.get_content_stream()
    assert isinstance(pd_stream, PDStream)
    # The PDStream wraps the same COSStream backing the pattern.
    assert pd_stream.get_cos_object() is pattern.get_cos_object()


# ---------------------------------------------------------------------------
# Paint-type / tiling-type predicate constants
# ---------------------------------------------------------------------------


def test_paint_type_constants_match_spec():
    # PDF 32000-1 §8.7.3.3 Table 75 — /PaintType: 1 (colored), 2 (uncolored).
    assert PDTilingPattern.PAINT_TYPE_COLORED == 1
    assert PDTilingPattern.PAINT_TYPE_UNCOLORED == 2
    # Older shorter aliases preserved for back-compat.
    assert PDTilingPattern.PAINT_COLORED == 1
    assert PDTilingPattern.PAINT_UNCOLORED == 2


def test_tiling_type_constants_match_spec():
    # PDF 32000-1 §8.7.3.3 Table 75 — /TilingType: 1, 2, 3.
    assert PDTilingPattern.TILING_TYPE_CONSTANT_SPACING == 1
    assert PDTilingPattern.TILING_TYPE_NO_DISTORTION == 2
    assert PDTilingPattern.TILING_TYPE_CONSTANT_SPACING_AND_FASTER_TILING == 3
    # Older shorter aliases.
    assert PDTilingPattern.TILING_CONSTANT_SPACING == 1
    assert PDTilingPattern.TILING_NO_DISTORTION == 2
    assert PDTilingPattern.TILING_CONSTANT_SPACING_FASTER_TILING == 3
