from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.pattern import (
    PDAbstractPattern,
    PDShadingPattern,
    PDTilingPattern,
)
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_BBOX = COSName.get_pdf_name("BBox")
_EXT_G_STATE = COSName.get_pdf_name("ExtGState")
_MATRIX = COSName.get_pdf_name("Matrix")
_PAINT_TYPE = COSName.get_pdf_name("PaintType")
_SHADING = COSName.get_pdf_name("Shading")
_X_STEP = COSName.get_pdf_name("XStep")
_Y_STEP = COSName.get_pdf_name("YStep")


# ---------- PDAbstractPattern ----------


def test_abstract_pattern_get_matrix_default_identity() -> None:
    """No ``/Matrix`` entry → identity matrix per PDF §8.7."""
    pattern = PDTilingPattern()
    assert pattern.get_cos_object().get_dictionary_object(_MATRIX) is None
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_abstract_pattern_set_matrix_round_trip() -> None:
    pattern = PDTilingPattern()
    pattern.set_matrix([2.0, 0.0, 0.0, 3.0, 10.0, 20.0])
    assert pattern.get_matrix() == [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]
    arr = pattern.get_cos_object().get_dictionary_object(_MATRIX)
    assert isinstance(arr, COSArray)
    assert arr.size() == 6


def test_abstract_pattern_set_matrix_clear_with_none() -> None:
    pattern = PDTilingPattern()
    pattern.set_matrix([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    pattern.set_matrix(None)
    assert pattern.get_cos_object().get_dictionary_object(_MATRIX) is None
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_abstract_pattern_set_matrix_rejects_wrong_length() -> None:
    pattern = PDTilingPattern()
    with pytest.raises(ValueError):
        pattern.set_matrix([1.0, 2.0, 3.0])


def test_abstract_pattern_get_ext_g_state_returns_typed_wrapper() -> None:
    pattern = PDShadingPattern()
    assert pattern.get_ext_g_state() is None

    extgs = PDExtendedGraphicsState()
    pattern.set_ext_g_state(extgs)
    out = pattern.get_ext_g_state()
    assert out is not None
    assert isinstance(out, PDExtendedGraphicsState)
    assert out.get_cos_object() is extgs.get_cos_object()
    assert (
        pattern.get_cos_object().get_dictionary_object(_EXT_G_STATE)
        is extgs.get_cos_object()
    )


def test_abstract_pattern_set_ext_g_state_accepts_raw_dict() -> None:
    pattern = PDShadingPattern()
    raw = COSDictionary()
    pattern.set_ext_g_state(raw)
    out = pattern.get_ext_g_state()
    assert out is not None
    assert out.get_cos_object() is raw


def test_abstract_pattern_set_ext_g_state_none_clears() -> None:
    pattern = PDShadingPattern()
    pattern.set_ext_g_state(PDExtendedGraphicsState())
    pattern.set_ext_g_state(None)
    assert pattern.get_ext_g_state() is None
    assert pattern.get_cos_object().get_dictionary_object(_EXT_G_STATE) is None


def test_abstract_pattern_set_ext_g_state_rejects_garbage() -> None:
    pattern = PDShadingPattern()
    with pytest.raises(TypeError):
        pattern.set_ext_g_state("not a dict")  # type: ignore[arg-type]


def test_abstract_pattern_type_predicates() -> None:
    tiling = PDTilingPattern()
    shading = PDShadingPattern()

    assert tiling.is_tiling_pattern() is True
    assert tiling.is_shading_pattern() is False

    assert shading.is_tiling_pattern() is False
    assert shading.is_shading_pattern() is True


# ---------- PDTilingPattern ----------


def test_tiling_paint_type_constants_match_spec() -> None:
    assert PDTilingPattern.PAINT_TYPE_COLORED == 1
    assert PDTilingPattern.PAINT_TYPE_UNCOLORED == 2


def test_tiling_tiling_type_constants_match_spec() -> None:
    assert PDTilingPattern.TILING_TYPE_CONSTANT_SPACING == 1
    assert PDTilingPattern.TILING_TYPE_NO_DISTORTION == 2
    assert (
        PDTilingPattern.TILING_TYPE_CONSTANT_SPACING_AND_FASTER_TILING == 3
    )


def test_tiling_paint_type_round_trip_typed_constants() -> None:
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_UNCOLORED)
    assert pattern.get_paint_type() == 2
    assert pattern.get_cos_object().get_int(_PAINT_TYPE, 0) == 2

    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    assert pattern.get_paint_type() == 1
    assert pattern.get_cos_object().get_int(_PAINT_TYPE, 0) == 1


def test_tiling_x_step_y_step_round_trip_typed() -> None:
    pattern = PDTilingPattern()
    pattern.set_x_step(48.0)
    pattern.set_y_step(96.0)
    assert pattern.get_x_step() == pytest.approx(48.0)
    assert pattern.get_y_step() == pytest.approx(96.0)
    assert pattern.get_cos_object().get_float(_X_STEP) == pytest.approx(48.0)
    assert pattern.get_cos_object().get_float(_Y_STEP) == pytest.approx(96.0)


def test_tiling_b_box_round_trip_typed_pdrectangle() -> None:
    pattern = PDTilingPattern()
    assert pattern.get_b_box() is None

    rect = PDRectangle(0.0, 0.0, 100.0, 200.0)
    pattern.set_b_box(rect)

    out = pattern.get_b_box()
    assert out is not None
    assert isinstance(out, PDRectangle)
    assert out.get_lower_left_x() == pytest.approx(0.0)
    assert out.get_lower_left_y() == pytest.approx(0.0)
    assert out.get_upper_right_x() == pytest.approx(100.0)
    assert out.get_upper_right_y() == pytest.approx(200.0)
    assert out.get_width() == pytest.approx(100.0)
    assert out.get_height() == pytest.approx(200.0)

    raw = pattern.get_cos_object().get_dictionary_object(_BBOX)
    assert isinstance(raw, COSArray)
    assert raw.size() == 4


def test_tiling_b_box_accepts_raw_cos_array() -> None:
    pattern = PDTilingPattern()
    arr = COSArray(
        [COSFloat(1.0), COSFloat(2.0), COSFloat(11.0), COSFloat(22.0)]
    )
    pattern.set_b_box(arr)
    out = pattern.get_b_box()
    assert out is not None
    assert out.get_lower_left_x() == pytest.approx(1.0)
    assert out.get_upper_right_y() == pytest.approx(22.0)


def test_tiling_b_box_none_clears() -> None:
    pattern = PDTilingPattern()
    pattern.set_b_box(PDRectangle(0.0, 0.0, 5.0, 5.0))
    pattern.set_b_box(None)
    assert pattern.get_b_box() is None
    assert pattern.get_cos_object().get_dictionary_object(_BBOX) is None


def test_tiling_b_box_rejects_garbage() -> None:
    pattern = PDTilingPattern()
    with pytest.raises(TypeError):
        pattern.set_b_box(42)  # type: ignore[arg-type]


# ---------- PDShadingPattern ----------


def test_shading_get_shading_wraps_dict_into_pdshading() -> None:
    pattern = PDShadingPattern()
    assert pattern.get_shading() is None

    raw = COSDictionary()
    raw.set_int("ShadingType", PDShading.SHADING_TYPE2)
    pattern.set_shading(raw)

    out = pattern.get_shading()
    assert out is not None
    assert isinstance(out, PDShading)
    assert out.get_cos_object() is raw
    assert out.get_shading_type() == PDShading.SHADING_TYPE2


def test_shading_set_shading_accepts_typed_pdshading() -> None:
    pattern = PDShadingPattern()
    raw = COSDictionary()
    raw.set_int("ShadingType", PDShading.SHADING_TYPE3)
    typed = PDShading.create(raw)
    assert typed is not None

    pattern.set_shading(typed)
    out = pattern.get_shading()
    assert out is not None
    assert out.get_cos_object() is raw
    assert (
        pattern.get_cos_object().get_dictionary_object(_SHADING) is raw
    )


def test_shading_set_shading_none_clears() -> None:
    pattern = PDShadingPattern()
    raw = COSDictionary()
    raw.set_int("ShadingType", PDShading.SHADING_TYPE1)
    pattern.set_shading(raw)
    pattern.set_shading(None)
    assert pattern.get_shading() is None
    assert pattern.get_cos_object().get_dictionary_object(_SHADING) is None


def test_shading_pattern_inherits_get_matrix_default_identity() -> None:
    pattern = PDShadingPattern()
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_shading_pattern_inherits_get_ext_g_state_typed() -> None:
    pattern = PDShadingPattern()
    extgs = PDExtendedGraphicsState()
    pattern.set_ext_g_state(extgs)
    out = pattern.get_ext_g_state()
    assert out is not None
    assert isinstance(out, PDExtendedGraphicsState)


# ---------- type-predicate cross-check via factory ----------


def test_factory_dispatch_preserves_type_predicates() -> None:
    from pypdfbox.cos import COSStream

    tiling_stream = COSStream()
    tiling_stream.set_int(COSName.get_pdf_name("PatternType"), 1)
    tiling = PDAbstractPattern.create(tiling_stream)
    assert tiling is not None
    assert tiling.is_tiling_pattern()
    assert not tiling.is_shading_pattern()

    shading_dict = COSDictionary()
    shading_dict.set_int(COSName.get_pdf_name("PatternType"), 2)
    shading = PDAbstractPattern.create(shading_dict)
    assert shading is not None
    assert shading.is_shading_pattern()
    assert not shading.is_tiling_pattern()


# ---------- new parity round-out (Wave 42) ----------


def test_abstract_pattern_get_type_constant() -> None:
    """``getType()`` is the spec-fixed string 'Pattern'."""
    assert PDTilingPattern().get_type() == "Pattern"
    assert PDShadingPattern().get_type() == "Pattern"


def test_abstract_pattern_set_pattern_type_writes_dict() -> None:
    """Base setter writes ``/PatternType`` even though concrete subclasses
    override the getter — mirrors upstream's
    ``PDAbstractPattern.setPatternType`` surface."""
    pattern = PDTilingPattern()
    pattern.set_pattern_type(7)
    assert (
        pattern.get_cos_object().get_int(COSName.get_pdf_name("PatternType"), 0)
        == 7
    )


def test_abstract_pattern_set_paint_type_on_base() -> None:
    """Upstream defines ``setPaintType`` on the base class — usable on a
    shading pattern even though the spec only defines /PaintType for
    tiling patterns."""
    shading = PDShadingPattern()
    shading.set_paint_type(1)
    assert (
        shading.get_cos_object().get_int(_PAINT_TYPE, 0) == 1
    )


def test_factory_dispatch_with_resource_cache_forwarded() -> None:
    """``PDAbstractPattern.create`` accepts a ``resource_cache`` kwarg and
    threads it through to ``PDTilingPattern`` (mirrors upstream's two-arg
    factory)."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

    cache = DefaultResourceCache()
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("PatternType"), 1)
    tiling = PDAbstractPattern.create(stream, resource_cache=cache)
    assert isinstance(tiling, PDTilingPattern)
    # The cache propagates down the resources lookup path; verify the
    # private attribute (no public getter on PDTilingPattern itself).
    assert tiling._resource_cache is cache  # type: ignore[attr-defined]


def test_tiling_get_content_stream_returns_pdstream() -> None:
    """``getContentStream`` wraps the pattern's COSStream as a PDStream."""
    from pypdfbox.pdmodel.common.pd_stream import PDStream

    pattern = PDTilingPattern()
    cs = pattern.get_content_stream()
    assert isinstance(cs, PDStream)
    assert cs.get_cos_stream() is pattern.get_cos_object()


def test_tiling_resources_carry_resource_cache() -> None:
    """The cache stashed at construction time is passed on to each
    ``PDResources`` instance returned by ``get_resources``."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

    cache = DefaultResourceCache()
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("PatternType"), 1)
    # Attach a /Resources subdictionary so get_resources returns non-None.
    stream.set_item(COSName.RESOURCES, COSDictionary())  # type: ignore[attr-defined]
    pattern = PDTilingPattern(stream, resource_cache=cache)
    res = pattern.get_resources()
    assert res is not None
    assert res._resource_cache is cache  # type: ignore[attr-defined]


# ---------- /Pattern color space dispatch (cross-cluster verification) ----------


def test_pattern_color_space_colored_form_has_no_underlying() -> None:
    """``PDPattern()`` (no underlying CS) — the colored / name form."""
    from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

    cs = PDPattern()
    assert cs.get_underlying_color_space() is None
    assert cs.get_name() == "Pattern"
    # Colored pattern serialises as the bare /Pattern name.
    assert cs.get_cos_object() == COSName.get_pdf_name("Pattern")


def test_pattern_color_space_uncolored_form_carries_underlying() -> None:
    """Uncolored tiling pattern → array form ``[/Pattern <CS>]``."""
    from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
    from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

    cs = PDPattern(PDDeviceRGB.INSTANCE)
    underlying = cs.get_underlying_color_space()
    assert underlying is PDDeviceRGB.INSTANCE
    out = cs.get_cos_object()
    assert isinstance(out, COSArray)
    assert out.size() == 2
    assert out.get_object(0) == COSName.get_pdf_name("Pattern")


def test_pattern_color_space_to_rgb_uncolored_recurses() -> None:
    """For an uncolored tiling pattern, ``to_rgb`` should recurse into the
    underlying color space (the components are tints)."""
    from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
    from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

    cs = PDPattern(PDDeviceRGB.INSTANCE)
    assert cs.to_rgb([0.5, 0.5, 0.5]) is not None


def test_pattern_color_space_to_rgb_colored_returns_none() -> None:
    """Colored patterns can't be reduced to a single RGB triple without
    rendering — ``to_rgb`` returns ``None`` so callers can short-circuit."""
    from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

    cs = PDPattern()
    assert cs.to_rgb([]) is None


# ---------- PDContentStream surface (Wave 43) ----------


def test_tiling_get_contents_returns_decoded_stream() -> None:
    """``getContents()`` returns a ``BinaryIO`` over the decoded body —
    mirrors upstream's ``PDContentStream.getContents``."""
    pattern = PDTilingPattern()
    cs = pattern.get_content_stream()
    with cs.create_output_stream() as out:
        out.write(b"q 1 0 0 1 0 0 cm Q")

    contents = pattern.get_contents()
    assert contents is not None
    data = contents.read()
    assert data == b"q 1 0 0 1 0 0 cm Q"


def test_tiling_get_contents_for_random_access_returns_raw_stream() -> None:
    """``getContentsForRandomAccess()`` returns a raw (encoded) seekable
    view — mirrors upstream's ``RandomAccessRead`` return."""
    pattern = PDTilingPattern()
    cs = pattern.get_content_stream()
    with cs.create_output_stream() as out:
        out.write(b"hello world")

    raw = pattern.get_contents_for_random_access()
    assert raw is not None
    # Raw view supports seek/read.
    raw.seek(0)
    assert raw.read() == b"hello world"


def test_tiling_get_contents_for_stream_parsing_delegates_to_raw_stream() -> None:
    """``getContentsForStreamParsing()`` follows upstream's default
    ``PDContentStream`` implementation and delegates to the random-access
    content stream."""
    pattern = PDTilingPattern()
    cs = pattern.get_content_stream()
    with cs.create_output_stream() as out:
        out.write(b"BT /F1 12 Tf ET")

    stream = pattern.get_contents_for_stream_parsing()
    assert stream is not None
    stream.seek(0)
    assert stream.read() == b"BT /F1 12 Tf ET"


def test_tiling_get_contents_returns_none_for_non_stream() -> None:
    """A pattern whose underlying COSDictionary isn't a stream → ``None``
    rather than raising — matches upstream's ``return null``."""
    from pypdfbox.cos import COSDictionary

    # Bypass the typed ctor so we can wrap a non-stream dictionary; this
    # is the only way to construct a degenerate PDTilingPattern.
    plain = COSDictionary()
    plain.set_int(COSName.get_pdf_name("PatternType"), 1)
    pattern = PDTilingPattern.__new__(PDTilingPattern)
    pattern._dict = plain  # type: ignore[attr-defined]
    pattern._resource_cache = None  # type: ignore[attr-defined]
    assert pattern.get_contents() is None
    assert pattern.get_contents_for_random_access() is None
    assert pattern.get_contents_for_stream_parsing() is None


# ---------- PDShadingPattern typed /ExtGState override ----------


def test_shading_get_extended_graphics_state_typed() -> None:
    """``PDShadingPattern.getExtendedGraphicsState`` returns a typed
    ``PDExtendedGraphicsState`` — overrides the base accessor that
    returns the raw dict."""
    pattern = PDShadingPattern()
    assert pattern.get_extended_graphics_state() is None

    extgs = PDExtendedGraphicsState()
    pattern.set_extended_graphics_state(extgs)
    out = pattern.get_extended_graphics_state()
    assert out is not None
    assert isinstance(out, PDExtendedGraphicsState)
    assert out.get_cos_object() is extgs.get_cos_object()


def test_shading_set_extended_graphics_state_accepts_raw_dict() -> None:
    pattern = PDShadingPattern()
    raw = COSDictionary()
    pattern.set_extended_graphics_state(raw)
    out = pattern.get_extended_graphics_state()
    assert out is not None
    assert isinstance(out, PDExtendedGraphicsState)
    assert out.get_cos_object() is raw


def test_shading_set_extended_graphics_state_none_clears() -> None:
    pattern = PDShadingPattern()
    pattern.set_extended_graphics_state(PDExtendedGraphicsState())
    pattern.set_extended_graphics_state(None)
    assert pattern.get_extended_graphics_state() is None
    assert pattern.get_cos_object().get_dictionary_object(_EXT_G_STATE) is None


def test_shading_set_extended_graphics_state_rejects_garbage() -> None:
    pattern = PDShadingPattern()
    with pytest.raises(TypeError):
        pattern.set_extended_graphics_state(42)  # type: ignore[arg-type]


# ---------- /Matrix permissive parsing (upstream Matrix.createMatrix parity) ----------


def test_get_matrix_returns_identity_when_entry_not_array() -> None:
    """Upstream ``Matrix.createMatrix`` returns identity when ``/Matrix`` is
    not a COSArray. Our port now mirrors that instead of relying on the
    base default-only path."""
    from pypdfbox.cos import COSInteger

    pattern = PDTilingPattern()
    pattern.get_cos_object().set_item(_MATRIX, COSInteger.get(7))
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_get_matrix_returns_identity_when_array_too_short() -> None:
    """Array shorter than 6 entries → identity (upstream parity)."""
    pattern = PDTilingPattern()
    arr = COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0)])
    pattern.get_cos_object().set_item(_MATRIX, arr)
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_get_matrix_returns_identity_when_entry_non_numeric() -> None:
    """Any non-numeric entry → identity (mirrors upstream
    ``Matrix.createMatrix``'s ``COSNumber`` instanceof loop)."""
    from pypdfbox.cos import COSName as _CN

    pattern = PDTilingPattern()
    arr = COSArray(
        [
            COSFloat(1.0),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(1.0),
            _CN.get_pdf_name("Bogus"),  # not numeric
            COSFloat(0.0),
        ]
    )
    pattern.get_cos_object().set_item(_MATRIX, arr)
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


# ---------- /Matrix AffineTransform-like adapter (upstream setMatrix parity) ----------


def test_set_matrix_accepts_affine_transform_like_adapter() -> None:
    """Upstream ``setMatrix(AffineTransform)`` extracts 6 floats via
    ``transform.getMatrix(double[])``. Our port duck-types: any object with
    a callable ``get_matrix()`` returning a 6-sequence is accepted."""

    class FakeAffineTransform:
        def get_matrix(self) -> list[float]:
            return [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]

    pattern = PDTilingPattern()
    pattern.set_matrix(FakeAffineTransform())
    assert pattern.get_matrix() == [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]
    arr = pattern.get_cos_object().get_dictionary_object(_MATRIX)
    assert isinstance(arr, COSArray)
    assert arr.size() == 6


def test_set_matrix_affine_transform_adapter_wrong_length_raises() -> None:
    class BadTransform:
        def get_matrix(self) -> list[float]:
            return [1.0, 2.0, 3.0]

    pattern = PDTilingPattern()
    with pytest.raises(ValueError):
        pattern.set_matrix(BadTransform())


def test_set_matrix_still_accepts_plain_sequence() -> None:
    """Plain 6-element sequence path still works — the duck-typed branch
    only fires for non-list/tuple objects exposing ``get_matrix``."""
    pattern = PDTilingPattern()
    pattern.set_matrix([1.5, 0.0, 0.0, 2.5, 5.0, 7.0])
    assert pattern.get_matrix() == [1.5, 0.0, 0.0, 2.5, 5.0, 7.0]


# ---------- Wave 234: PDTilingPattern /PaintType predicates ----------


def test_tiling_is_colored_default_false_when_paint_type_unset() -> None:
    """Fresh pattern has no ``/PaintType`` (defaults to 0); both predicates
    must return ``False`` so callers don't mistake a default-zero value for
    either spec-defined paint type."""
    pattern = PDTilingPattern()
    assert pattern.get_paint_type() == 0
    assert pattern.is_colored() is False
    assert pattern.is_uncolored() is False


def test_tiling_is_colored_true_when_paint_type_one() -> None:
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    assert pattern.is_colored() is True
    assert pattern.is_uncolored() is False


def test_tiling_is_uncolored_true_when_paint_type_two() -> None:
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_UNCOLORED)
    assert pattern.is_uncolored() is True
    assert pattern.is_colored() is False


def test_tiling_paint_type_predicates_false_for_unknown_value() -> None:
    """Unknown paint-type values (e.g. corrupted PDF with /PaintType 99) →
    both predicates ``False``, never raise."""
    pattern = PDTilingPattern()
    pattern.set_paint_type(99)
    assert pattern.is_colored() is False
    assert pattern.is_uncolored() is False


# ---------- Wave 234: PDTilingPattern /TilingType predicates ----------


def test_tiling_tiling_type_predicates_default_false_when_unset() -> None:
    """Fresh pattern has no ``/TilingType`` (defaults to 0); all three
    predicates must return ``False``."""
    pattern = PDTilingPattern()
    assert pattern.get_tiling_type() == 0
    assert pattern.is_constant_spacing() is False
    assert pattern.is_no_distortion() is False
    assert pattern.is_constant_spacing_and_faster_tiling() is False


def test_tiling_is_constant_spacing_true_when_tiling_type_one() -> None:
    pattern = PDTilingPattern()
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    assert pattern.is_constant_spacing() is True
    assert pattern.is_no_distortion() is False
    assert pattern.is_constant_spacing_and_faster_tiling() is False


def test_tiling_is_no_distortion_true_when_tiling_type_two() -> None:
    pattern = PDTilingPattern()
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_NO_DISTORTION)
    assert pattern.is_constant_spacing() is False
    assert pattern.is_no_distortion() is True
    assert pattern.is_constant_spacing_and_faster_tiling() is False


def test_tiling_is_constant_spacing_and_faster_tiling_true_when_three() -> None:
    pattern = PDTilingPattern()
    pattern.set_tiling_type(
        PDTilingPattern.TILING_TYPE_CONSTANT_SPACING_AND_FASTER_TILING
    )
    assert pattern.is_constant_spacing() is False
    assert pattern.is_no_distortion() is False
    assert pattern.is_constant_spacing_and_faster_tiling() is True


def test_tiling_tiling_type_predicates_false_for_unknown_value() -> None:
    pattern = PDTilingPattern()
    pattern.set_tiling_type(42)
    assert pattern.is_constant_spacing() is False
    assert pattern.is_no_distortion() is False
    assert pattern.is_constant_spacing_and_faster_tiling() is False


# ---------- Wave 234: PDTilingPattern.has_b_box ----------


def test_tiling_has_b_box_false_when_missing() -> None:
    pattern = PDTilingPattern()
    assert pattern.has_b_box() is False


def test_tiling_has_b_box_true_after_set() -> None:
    pattern = PDTilingPattern()
    pattern.set_b_box(PDRectangle(0.0, 0.0, 50.0, 50.0))
    assert pattern.has_b_box() is True


def test_tiling_has_b_box_false_after_clear() -> None:
    pattern = PDTilingPattern()
    pattern.set_b_box(PDRectangle(0.0, 0.0, 50.0, 50.0))
    pattern.set_b_box(None)
    assert pattern.has_b_box() is False


def test_tiling_has_b_box_false_when_array_too_short() -> None:
    """Array shorter than 4 entries is malformed — both ``has_b_box`` and
    ``get_b_box`` must reject it."""
    pattern = PDTilingPattern()
    bad = COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0)])
    pattern.get_cos_object().set_item(_BBOX, bad)
    assert pattern.has_b_box() is False
    assert pattern.get_b_box() is None


def test_tiling_has_b_box_false_when_entry_not_array() -> None:
    """Non-COSArray entry → ``has_b_box`` returns ``False``."""
    from pypdfbox.cos import COSInteger

    pattern = PDTilingPattern()
    pattern.get_cos_object().set_item(_BBOX, COSInteger.get(7))
    assert pattern.has_b_box() is False


# ---------- Wave 234: PDShadingPattern.has_shading ----------


def test_shading_has_shading_false_when_missing() -> None:
    pattern = PDShadingPattern()
    assert pattern.has_shading() is False


def test_shading_has_shading_true_after_set() -> None:
    pattern = PDShadingPattern()
    raw = COSDictionary()
    raw.set_int("ShadingType", PDShading.SHADING_TYPE2)
    pattern.set_shading(raw)
    assert pattern.has_shading() is True


def test_shading_has_shading_false_after_clear() -> None:
    pattern = PDShadingPattern()
    raw = COSDictionary()
    raw.set_int("ShadingType", PDShading.SHADING_TYPE1)
    pattern.set_shading(raw)
    pattern.set_shading(None)
    assert pattern.has_shading() is False


def test_shading_has_shading_false_when_entry_not_dictionary() -> None:
    """If ``/Shading`` is present but not a dictionary (corrupted PDF),
    ``has_shading`` must return ``False`` so callers know there's no
    typed wrapper to retrieve."""
    from pypdfbox.cos import COSInteger

    pattern = PDShadingPattern()
    pattern.get_cos_object().set_item(_SHADING, COSInteger.get(3))
    assert pattern.has_shading() is False
    assert pattern.get_shading() is None
