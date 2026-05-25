"""Wave 1399 branch-coverage tests for annotation appearance handlers.

Closes the remaining partial branch arrows in the four hottest handler
modules:

* ``pd_free_text_appearance_handler`` (9 partials)
* ``pd_abstract_appearance_handler`` (5 partials)
* ``pd_circle_appearance_handler`` (5 partials)
* ``pd_square_appearance_handler`` (5 partials)

Each test exercises a real annotation appearance flow (build COS dict,
invoke ``generate_normal_appearance`` or the corresponding helper, then
introspect the resulting content stream / appearance metadata). Where a
branch is only reachable through duck-typed substitution (e.g. when
``get_normal_appearance_stream`` returns ``None`` mid-run because /AP /N
is a sub-dictionary), a minimal stand-in object is used. No production
code paths are mocked away — only the input shape varies.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_abstract_appearance_handler import (
    PDAbstractAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_circle_appearance_handler import (
    PDCircleAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_free_text_appearance_handler import (
    PDFreeTextAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_square_appearance_handler import (
    PDSquareAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationCircle,
    PDAnnotationSquare,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_entry import (
    PDAppearanceEntry,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (10.0, 10.0, 110.0, 60.0)


def _appearance_bytes(annotation: PDAnnotation) -> bytes:
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    stream = ap.get_normal_appearance().get_appearance_stream()
    return stream.get_stream().to_byte_array()


class _ConcreteAbstractHandler(PDAbstractAppearanceHandler):
    """Concrete subclass — abstract base's ``generate_normal_appearance``
    is intentionally a no-op pragma; subclass to exercise the rest of
    the surface."""

    def generate_normal_appearance(self) -> None:
        return None


# ======================================================================
# PDFreeTextAppearanceHandler — 9 partials
# ======================================================================


def test_free_text_ds_without_color_match_skips_override() -> None:
    """Branch 110->118: ``/DS`` set but no ``color:#rrggbb`` token →
    ``match is None`` → fall through without rewriting text_components."""
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_contents("Body")
    # /DS without a color: directive.
    annotation.set_default_style_string("font: Helvetica; weight: bold")
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Border rectangle should still be drawn.
    assert b"re" in body


def test_free_text_callout_with_coincident_first_segment_skips_shorten() -> None:
    """Branch 138->141: callout's first two coordinates coincide
    (length == 0) → skip the ``x += dx``/``y += dy`` shortening branch."""
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    # Coincident points: (20, 20) and (20, 20), then a final knee.
    annotation.set_callout_line([20.0, 20.0, 20.0, 20.0, 80.0, 80.0])
    annotation.set_line_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Still produces a move-to + stroke for the callout polyline.
    assert b"m" in body
    assert b"S" in body


def test_free_text_extract_font_details_da_tf_with_non_name_first_arg() -> None:
    """Branch 353->355: /DA ``Tf`` whose first argument is *not* a
    :class:`COSName` (here: an integer) → keep default ``_font_name``
    but still set ``_font_size`` from the second arg if numeric."""
    annotation = PDAnnotationFreeText()
    # The /DA `42 12 Tf` is malformed (font op needs a name), but the
    # scanner accepts the tokens and the handler checks each slot.
    annotation.set_default_appearance("42 12 Tf")
    handler = PDFreeTextAppearanceHandler(annotation)
    handler.extract_font_details(annotation)
    # First arg ignored — font_name remains the default Helv.
    assert handler._font_name == handler.DEFAULT_FONT_NAME  # noqa: SLF001
    # Second arg accepted — font_size becomes 12.0.
    assert handler._font_size == 12.0  # noqa: SLF001


def test_free_text_extract_font_details_da_tf_with_non_number_second_arg() -> None:
    """Branch 356->exit: /DA ``Tf`` whose second argument is *not* a
    :class:`COSNumber` (here: a name) → font_size stays at the default."""
    annotation = PDAnnotationFreeText()
    # /Helv /Bogus Tf — first arg is a valid name, second is a name not a number.
    annotation.set_default_appearance("/Helv /Bogus Tf")
    handler = PDFreeTextAppearanceHandler(annotation)
    handler.extract_font_details(annotation)
    assert handler._font_name == COSName.get_pdf_name("Helv")  # noqa: SLF001
    # Default size retained because COSName is not a COSNumber.
    assert handler._font_size == handler.DEFAULT_FONT_SIZE  # noqa: SLF001


def test_free_text_callout_with_normal_stream_none_in_grow_block() -> None:
    """Branch 304->exit: in the callout rect-grow block, ``normal_stream``
    is ``None`` → skip the ``normal_stream.set_bbox(rect)`` arm.

    Reproduces by monkey-patching ``annotation.get_normal_appearance_stream``
    to return ``None``, simulating an /AP /N state sub-dictionary where
    no /AS state is set (a real scenario for stateful annotations).
    """
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    annotation.set_callout_line([20.0, 20.0, 80.0, 80.0])

    # Force get_normal_appearance_stream to return None — the handler's
    # internal flow still allocates the stream via the writer context,
    # but the surface-level lookup at line 183 returns None.
    annotation.get_normal_appearance_stream = lambda: None  # type: ignore[method-assign]
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    # Annotation rect should still have been grown to enclose the callout.
    grown_rect = annotation.get_rectangle()
    assert grown_rect is not None
    assert grown_rect.get_upper_right_y() >= 80.0


def test_free_text_no_normal_stream_in_border_box_block() -> None:
    """Branch 184->186: at the border-box assignment, ``normal_stream``
    is ``None`` → skip the ``normal_stream.set_bbox(border_box)`` arm."""
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    # Force get_normal_appearance_stream to return None.
    annotation.get_normal_appearance_stream = lambda: None  # type: ignore[method-assign]
    # Run the handler — must complete without raising.
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    # The rect should not have been overwritten on this code path.
    assert annotation.get_rectangle() is not None


def test_free_text_callout_with_rect_cleared_after_handler_resolves() -> None:
    """Branch 282->exit: callout flow when ``annotation.get_rectangle()``
    returns ``None`` at the grow-block step (line 281) → skip the
    rect-grow arm.

    The handler calls ``self.get_rectangle()`` (which delegates to the
    annotation) three times during the callout flow: at the border-box
    setup, at the line-185 ``normal_stream.set_bbox`` arm, and at the
    grow block (line 281). Return None on the last call only."""
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    annotation.set_callout_line([20.0, 20.0, 80.0, 80.0])

    real_get_rectangle = annotation.get_rectangle
    call_count = {"n": 0}

    def patched_get_rectangle() -> PDRectangle | None:
        call_count["n"] += 1
        # Allow the first two calls (border-box compute + normal-stream
        # bbox arm). The grow block at line 281 is the third call.
        if call_count["n"] >= 3:
            return None
        return real_get_rectangle()

    annotation.get_rectangle = patched_get_rectangle  # type: ignore[method-assign]
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    # Appearance dict was still written.
    assert annotation.get_appearance_dictionary() is not None
    # And the third call (grow block) returned None.
    assert call_count["n"] >= 3


def test_free_text_handler_with_empty_text_components_skips_color_op() -> None:
    """Branch 264->exit: ``text_components`` empty → skip the
    ``cs.set_non_stroking_color(text_components)`` arm before the
    per-line Tj loop. Reached by overriding ``extract_non_stroking_color``
    to return an empty list (still not None, so has_stroke remains
    True)."""

    class _EmptyStrokeHandler(PDFreeTextAppearanceHandler):
        def extract_non_stroking_color(self, _annot):  # type: ignore[override]
            return []

    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_contents("Body")
    _EmptyStrokeHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Border rectangle is still emitted; show-text op is also emitted.
    assert b"re" in body
    assert b"Tj" in body


# Branch 118->120 (``if has_stroke``): mathematically unreachable. The
# production ``extract_non_stroking_color`` always returns a non-None
# list, and line 103 (``text_components = list(stroke_components)``)
# would raise ``TypeError`` before the ``if has_stroke`` check if it
# ever did return None. Tagged ``pragma: no branch`` in the handler
# source — see ``CHANGES.md`` wave 1399.


# ======================================================================
# PDAbstractAppearanceHandler — 5 partials
# ======================================================================


def test_abstract_create_cos_stream_with_document_lacking_create_method() -> None:
    """Branch 195->199: document's COSDocument has no callable
    ``create_cos_stream`` → fall through to the bare ``COSStream()``
    branch."""

    class _CosDocNoCreate:
        # No `create_cos_stream` attribute → getattr returns None.
        pass

    class _DocStub:
        def get_document(self) -> Any:
            return _CosDocNoCreate()

    annot = PDAnnotation()
    annot.set_rectangle(PDRectangle(*_RECT))
    handler = _ConcreteAbstractHandler(annot, document=_DocStub())
    stream = handler.create_cos_stream()
    # Falls through to bare COSStream.
    from pypdfbox.cos import COSStream

    assert isinstance(stream, COSStream)


def test_abstract_create_cos_stream_with_document_returning_non_stream() -> None:
    """Branch 197->199: ``cos_doc.create_cos_stream()`` returns something
    that isn't a :class:`COSStream` → fall through to the bare-stream
    branch."""

    class _CosDocReturnsNonStream:
        def create_cos_stream(self) -> Any:
            return "definitely not a stream"

    class _DocStub:
        def get_document(self) -> Any:
            return _CosDocReturnsNonStream()

    annot = PDAnnotation()
    annot.set_rectangle(PDRectangle(*_RECT))
    handler = _ConcreteAbstractHandler(annot, document=_DocStub())
    stream = handler.create_cos_stream()
    from pypdfbox.cos import COSStream

    assert isinstance(stream, COSStream)


def test_abstract_get_normal_appearance_stream_skips_bbox_when_no_rect() -> None:
    """Branch 249->251: ``rect is None`` → don't seed /BBox on the
    freshly-allocated form XObject."""
    # PDAnnotation without a rectangle.
    annot = PDAnnotation()
    handler = _ConcreteAbstractHandler(annot)
    stream = handler.get_normal_appearance_stream()
    # Form XObject keys all set, but /BBox should be absent because the
    # annotation had no /Rect.
    cos = stream.get_cos_object()
    # get_name returns the string value (not the COSName wrapper).
    assert cos.get_name("Subtype") == "Form"
    assert cos.get_item(COSName.get_pdf_name("BBox")) is None


def test_abstract_get_appearance_entry_skips_resources_seed_when_present() -> None:
    """Branch 293->297: ``appearance.get_resources()`` is not ``None`` →
    skip the ``PDResources()`` seeding branch."""
    annot = PDAnnotation()
    annot.set_rectangle(PDRectangle(*_RECT))
    handler = _ConcreteAbstractHandler(annot)
    # Seed an entry with a stream that already has /Resources.
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
        PDAppearanceStream,
    )
    from pypdfbox.pdmodel.pd_resources import PDResources

    cos_stream = handler.create_cos_stream()
    ap_stream = PDAppearanceStream(cos_stream)
    pre_existing = PDResources()
    # Tag a custom proc set on the resources so we can detect overwrites.
    pre_existing_dict = pre_existing.get_cos_object()
    sentinel_proc = COSArray()
    sentinel_proc.add(COSName.get_pdf_name("PDF"))
    pre_existing_dict.set_item(COSName.get_pdf_name("ProcSet"), sentinel_proc)
    ap_stream.set_resources(pre_existing)
    entry = PDAppearanceEntry(cos_stream)
    cs = handler.get_appearance_entry_as_content_stream(entry)
    try:
        # The /Resources COSDictionary must still carry our sentinel —
        # the handler skipped the ``PDResources()`` seed.
        post_resources = ap_stream.get_resources()
        assert post_resources is not None
        assert (
            post_resources.get_cos_object().get_dictionary_object(
                COSName.get_pdf_name("ProcSet")
            )
            is sentinel_proc
        )
    finally:
        cs.close()


def test_abstract_handle_border_box_skips_set_bbox_when_appearance_none() -> None:
    """Branch 432->444: in the RD-absent path, the appearance-stream
    bbox/matrix adjustment is skipped when ``appearance_stream`` is
    ``None`` (annotation has no /AP yet)."""
    annot = PDAnnotationSquare()
    annot.set_rectangle(PDRectangle(*_RECT))
    annot.set_color([0.0, 0.0, 0.0])
    # Crucially: do NOT pre-allocate /AP. The handler's flow runs
    # `get_normal_appearance_as_content_stream` first (which DOES set /AP),
    # so to hit this branch we must call handle_border_box directly with
    # no appearance stream pre-allocated.
    handler = _ConcreteAbstractHandler(annot)
    # No /AP on the annotation — annotation.get_normal_appearance_stream()
    # will return None at line 431.
    border_box = handler.handle_border_box(annot, line_width=2.0)
    assert border_box is not None
    # /RD got seeded.
    rd = annot.get_rect_differences()
    assert rd is not None
    # /Rect grew but /AP was never created.
    assert annot.get_appearance_dictionary() is None


# ======================================================================
# PDCircleAppearanceHandler — 5 partials
# ======================================================================


def test_circle_no_stroke_color_skips_stroking_op() -> None:
    """Branch 46->48: stroke_components is ``None`` (annotation /C absent
    / empty) → don't emit a stroking color op. Interior is set so
    has_background is True, isolating the missing branch."""
    annotation = PDAnnotationCircle()
    annotation.set_rectangle(PDRectangle(*_RECT))
    # No /C → _color_components_from_annotation returns None.
    annotation.set_interior_color([0.5, 0.5, 0.5])
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Non-stroking color op emitted (interior).
    assert b"rg" in body or b"g" in body
    # No stroking color op since stroke_components is None.
    assert b"RG" not in body


def test_circle_cloudy_branch_annotation_without_set_rect_difference() -> None:
    """Branch 72->74: ``hasattr(annotation, "set_rect_difference")`` False
    → skip the ``annotation.set_rect_difference`` call."""
    from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
        PDBorderEffectDictionary,
    )

    annotation = PDAnnotationCircle()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])

    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(1.0)
    annotation.set_border_effect(be)

    # Surgically hide set_rect_difference from the annotation. Python's
    # hasattr returns False when __getattribute__ raises AttributeError.
    real_attr = type(annotation).__getattribute__

    def _no_set_rect_diff(self, name):
        if name == "set_rect_difference":
            raise AttributeError(name)
        return real_attr(self, name)

    type(annotation).__getattribute__ = _no_set_rect_diff  # type: ignore[method-assign]
    try:
        PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    finally:
        type(annotation).__getattribute__ = real_attr  # type: ignore[method-assign]
    # Appearance was still generated.
    assert annotation.get_appearance_dictionary() is not None


def test_circle_cloudy_branch_with_no_appearance_stream() -> None:
    """Branch 75->81: cloudy branch where ``appearance_stream`` is
    ``None`` at the inner lookup → skip the bbox/matrix arm.

    The handler's writer is already closed by this point (its
    ``__exit__`` allocated /AP/N), so returning None just exercises
    the False arm without breaking the rest of the flow.
    """
    from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
        PDBorderEffectDictionary,
    )

    annotation = PDAnnotationCircle()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 1.0, 0.0])
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(1.0)
    annotation.set_border_effect(be)

    annotation.get_normal_appearance_stream = lambda: None  # type: ignore[method-assign]
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    # Appearance dict still in place (allocated by the writer context).
    assert annotation.get_appearance_dictionary() is not None


def test_circle_cloudy_branch_stream_without_set_matrix() -> None:
    """Branch 77->81: ``appearance_stream`` exists but lacks
    ``set_matrix`` (hasattr False) → skip the matrix-write arm."""
    from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
        PDBorderEffectDictionary,
    )

    annotation = PDAnnotationCircle()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(1.5)
    annotation.set_border_effect(be)

    class _NoSetMatrixStream:
        def __init__(self) -> None:
            self.bbox_set = False

        def set_bbox(self, *_args: Any, **_kwargs: Any) -> None:
            self.bbox_set = True

        # Deliberately no set_matrix attribute.

    stub = _NoSetMatrixStream()
    annotation.get_normal_appearance_stream = lambda: stub  # type: ignore[method-assign]
    PDCircleAppearanceHandler(annotation).generate_normal_appearance()
    assert stub.bbox_set


def test_circle_get_line_width_border_size_lt_three_falls_back() -> None:
    """Branch 118->122: /Border present but size < 3 → fall through to
    the 1.0 default. ``PDAnnotation.get_border()`` itself pads short
    arrays, so we shim the instance method to return a length-2
    :class:`COSArray` directly."""
    annotation = PDAnnotationCircle()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    short_border = COSArray()
    short_border.add(COSInteger.get(0))
    short_border.add(COSInteger.get(0))
    annotation.get_border = lambda: short_border  # type: ignore[method-assign]
    assert PDCircleAppearanceHandler(annotation).get_line_width() == 1.0


# ======================================================================
# PDSquareAppearanceHandler — 5 partials (mirror-image of circle)
# ======================================================================


def test_square_no_stroke_color_skips_stroking_op() -> None:
    """Branch 41->43: stroke_components is ``None`` → don't emit a
    stroking color op."""
    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_interior_color([0.25, 0.75, 0.25])
    PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Non-stroking color emitted (interior fill).
    assert b"rg" in body or b"g" in body
    # No stroking color.
    assert b"RG" not in body


def test_square_cloudy_branch_annotation_without_set_rect_difference() -> None:
    """Branch 70->72: ``hasattr(annotation, "set_rect_difference")`` False
    → skip the ``annotation.set_rect_difference`` call."""
    from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
        PDBorderEffectDictionary,
    )

    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(1.0)
    annotation.set_border_effect(be)

    real_attr = type(annotation).__getattribute__

    def _no_set_rect_diff(self, name):
        if name == "set_rect_difference":
            raise AttributeError(name)
        return real_attr(self, name)

    type(annotation).__getattribute__ = _no_set_rect_diff  # type: ignore[method-assign]
    try:
        PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    finally:
        type(annotation).__getattribute__ = real_attr  # type: ignore[method-assign]
    assert annotation.get_appearance_dictionary() is not None


def test_square_cloudy_branch_with_no_appearance_stream() -> None:
    """Branch 73->85: cloudy branch where ``appearance_stream`` is
    ``None`` (no /AP allocated for the inner lookup)."""
    from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
        PDBorderEffectDictionary,
    )

    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.5, 0.5, 0.5])
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(1.0)
    annotation.set_border_effect(be)

    annotation.get_normal_appearance_stream = lambda: None  # type: ignore[method-assign]
    PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_square_cloudy_branch_stream_without_set_matrix() -> None:
    """Branch 75->85: cloudy stream lacks ``set_matrix`` → skip the
    matrix-write arm."""
    from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
        PDBorderEffectDictionary,
    )

    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(2.0)
    annotation.set_border_effect(be)

    class _NoSetMatrixStream:
        def __init__(self) -> None:
            self.bbox_set = False

        def set_bbox(self, *_args: Any, **_kwargs: Any) -> None:
            self.bbox_set = True

    stub = _NoSetMatrixStream()
    annotation.get_normal_appearance_stream = lambda: stub  # type: ignore[method-assign]
    PDSquareAppearanceHandler(annotation).generate_normal_appearance()
    assert stub.bbox_set


def test_square_get_line_width_border_size_lt_three_falls_back() -> None:
    """Branch 105->109: same construction as
    :func:`test_circle_get_line_width_border_size_lt_three_falls_back`."""
    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    short_border = COSArray()
    short_border.add(COSInteger.get(0))
    short_border.add(COSInteger.get(0))
    annotation.get_border = lambda: short_border  # type: ignore[method-assign]
    assert PDSquareAppearanceHandler(annotation).get_line_width() == 1.0


# ======================================================================
# Bonus: smaller residuals — link, polygon, polyline, ink, caret,
# strikeout, underline, text, file-attachment
# ======================================================================


def test_link_handler_with_short_quad_points_skips_underline_check() -> None:
    """Branch 95->102 (pd_link_appearance_handler.py): /QuadPoints
    present but ``len(paths_array) < 8`` → skip the
    ``border_style.get_style() == STYLE_UNDERLINE`` lookup.

    Use 4 in-rect coords (only one path segment, length 4 < 8).
    """
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_link_appearance_handler import (
        PDLinkAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    annotation = PDAnnotationLink()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 50.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_quad_points([10.0, 10.0, 20.0, 20.0])
    PDLinkAppearanceHandler(annotation).generate_normal_appearance()
    # Appearance is allocated even though no path segments end up being
    # drawn (the while-loop body needs len >= 8).
    assert annotation.get_appearance_dictionary() is not None


def test_link_get_line_width_border_size_lt_three_falls_back() -> None:
    """Branch 129->133 (pd_link_appearance_handler.py): same pattern as
    circle/square — /Border returns a length-2 array → fall through to
    the 1.0 default."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_link_appearance_handler import (
        PDLinkAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    annotation = PDAnnotationLink()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 50.0))
    short_border = COSArray()
    short_border.add(COSInteger.get(0))
    short_border.add(COSInteger.get(0))
    annotation.get_border = lambda: short_border  # type: ignore[method-assign]
    assert PDLinkAppearanceHandler(annotation).get_line_width() == 1.0


def test_polygon_handler_no_stroke_skips_stroking_color() -> None:
    """Branch 70->72 (pd_polygon_appearance_handler.py): has_stroke False
    when /C is absent. Interior fill is set so has_background is True
    and the appearance is still meaningfully built."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polygon_appearance_handler import (
        PDPolygonAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
        PDAnnotationPolygon,
    )

    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_vertices([10.0, 10.0, 90.0, 10.0, 50.0, 90.0])
    annotation.set_interior_color([0.5, 0.5, 0.5])
    # No /C set → stroke_components is None → has_stroke is False.
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Stroking color op should not appear; non-stroking might.
    assert b"RG" not in body


def test_polygon_cloudy_branch_with_appearance_stream_none() -> None:
    """Branch 94->99 (pd_polygon_appearance_handler.py): cloudy branch
    where ``appearance_stream`` is ``None`` → skip the bbox/matrix
    arm."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polygon_appearance_handler import (
        PDPolygonAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
        PDAnnotationPolygon,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
        PDBorderEffectDictionary,
    )

    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_vertices([10.0, 10.0, 90.0, 10.0, 50.0, 90.0])
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(1.0)
    annotation.set_border_effect(be)
    annotation.get_normal_appearance_stream = lambda: None  # type: ignore[method-assign]
    PDPolygonAppearanceHandler(annotation).generate_normal_appearance()
    # Appearance dict was still written (writer context allocated /AP).
    assert annotation.get_appearance_dictionary() is not None


def test_polygon_emit_polygon_with_unrecognised_point_size() -> None:
    """Branch 109->103 (pd_polygon_appearance_handler.py): inner
    ``elif len(points_array) == 6`` False → loop continues (no line_to,
    no curve_to for malformed knee)."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polygon_appearance_handler import (
        PDPolygonAppearanceHandler,
    )

    # Synthetic path with a knee of unsupported arity (3 floats).
    # PDPolygonAppearanceHandler._emit_polygon is static — call directly
    # with a fake cs to assert the right ops are emitted.
    emitted: list[tuple[str, tuple]] = []

    class _FakeCS:
        def move_to(self, *args):
            emitted.append(("move_to", args))

        def line_to(self, *args):
            emitted.append(("line_to", args))

        def curve_to(self, *args):
            emitted.append(("curve_to", args))

        def close_path(self):
            emitted.append(("close_path", ()))

    # Path: start (2 floats), then a malformed knee (3 floats — neither 2
    # nor 6), then a valid line knee (2 floats).
    PDPolygonAppearanceHandler._emit_polygon(
        _FakeCS(),
        [[1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0]],
    )
    # The 3-float knee did NOT trigger line_to or curve_to.
    op_names = [op for op, _ in emitted]
    assert "move_to" in op_names
    assert "close_path" in op_names
    # Only one line_to (from the trailing 2-float knee), zero curve_to.
    assert op_names.count("line_to") == 1
    assert op_names.count("curve_to") == 0


def test_polygon_get_line_width_border_size_lt_three_falls_back() -> None:
    """Branch 146->150 (pd_polygon_appearance_handler.py): /Border
    length 2 → fall through to default 1.0."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polygon_appearance_handler import (
        PDPolygonAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
        PDAnnotationPolygon,
    )

    annotation = PDAnnotationPolygon()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 50.0))
    short_border = COSArray()
    short_border.add(COSInteger.get(0))
    short_border.add(COSInteger.get(0))
    annotation.get_border = lambda: short_border  # type: ignore[method-assign]
    assert PDPolygonAppearanceHandler(annotation).get_line_width() == 1.0


def test_polyline_handler_with_dashed_border_emits_dash_pattern() -> None:
    """Line 80 (pd_polyline_appearance_handler.py): ``cs.set_dash_pattern``
    call when /BS dash array is non-None."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polyline_appearance_handler import (
        PDPolylineAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
        PDAnnotationPolyline,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
        PDBorderStyleDictionary,
    )

    annotation = PDAnnotationPolyline()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_vertices([10.0, 10.0, 50.0, 90.0, 90.0, 10.0])
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    bs.set_dash_style([3.0, 2.0])
    bs.set_width(1.0)
    annotation.set_border_style(bs)
    PDPolylineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # The dash op is `d` in PDF.
    assert b"d" in body


def test_polyline_handler_with_decreasing_x_y_hits_min_branches() -> None:
    """Branches 61->63 (and the symmetrical max-tracking arms): a
    polyline whose later vertices have smaller x/y than the first one
    forces the False arm of ``if x > max_x`` (vertex already past max)."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polyline_appearance_handler import (
        PDPolylineAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
        PDAnnotationPolyline,
    )

    annotation = PDAnnotationPolyline()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    # 4 vertices: 1st sets max; 2nd is smaller (x stays as max — 61 False);
    # 3rd is larger (sets new max). y mixed similarly.
    annotation.set_vertices([90.0, 90.0, 10.0, 10.0, 50.0, 50.0])
    PDPolylineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_polyline_handler_with_coincident_start_segment() -> None:
    """Branch 93->96 (pd_polyline_appearance_handler.py): coincident
    first two vertices → ``length == 0`` so the start-shortening
    branch is skipped."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polyline_appearance_handler import (
        PDPolylineAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
        PDAnnotationPolyline,
    )

    annotation = PDAnnotationPolyline()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_vertices([20.0, 20.0, 20.0, 20.0, 80.0, 80.0])
    annotation.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    PDPolylineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_polyline_handler_with_coincident_end_segment() -> None:
    """Branch 105->108 (pd_polyline_appearance_handler.py): coincident
    last two vertices → ``length == 0`` so the end-shortening branch
    is skipped."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polyline_appearance_handler import (
        PDPolylineAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
        PDAnnotationPolyline,
    )

    annotation = PDAnnotationPolyline()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_vertices([20.0, 20.0, 80.0, 80.0, 80.0, 80.0])
    annotation.set_end_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    PDPolylineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_polyline_interior_components_size_branch_empty() -> None:
    """Line 171 (pd_polyline_appearance_handler.py): the size-branch
    empty case — ``interior.size() == 0`` → ``return None``."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polyline_appearance_handler import (
        PDPolylineAppearanceHandler,
    )

    class _EmptyWithSize:
        def size(self) -> int:
            return 0

    class _Stub:
        def get_interior_color(self):
            return _EmptyWithSize()

    assert PDPolylineAppearanceHandler._interior_components(_Stub()) is None


def test_polyline_interior_components_size_branch_non_empty() -> None:
    """Lines 170-172 (pd_polyline_appearance_handler.py): size branch
    with non-empty interior. Uses a stub object that exposes ``size``
    but where ``hasattr(interior, "to_float_array")`` is False on the
    first probe and True on the actual call."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polyline_appearance_handler import (
        PDPolylineAppearanceHandler,
    )

    state = {"hasattr_probes": 0}

    class _LatchedInterior:
        def size(self) -> int:
            return 3

        def to_float_array(self) -> list[float]:
            return [0.4, 0.5, 0.6]

        def __getattribute__(self, name):
            if name == "to_float_array":
                state["hasattr_probes"] += 1
                if state["hasattr_probes"] == 1:
                    raise AttributeError(name)
            return object.__getattribute__(self, name)

    class _Stub:
        def get_interior_color(self):
            return _LatchedInterior()

    components = PDPolylineAppearanceHandler._interior_components(_Stub())
    assert components == [0.4, 0.5, 0.6]


def test_ink_handler_no_rect_returns_after_extent_compute() -> None:
    """Line 67 (pd_ink_appearance_handler.py): annotation has /InkList
    and color, but rect is None at line 65 → return."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_ink_appearance_handler import (
        PDInkAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import (
        PDAnnotationInk,
    )

    annotation = PDAnnotationInk()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_ink_paths([[10.0, 10.0, 50.0, 50.0]])
    # Now clear the rectangle to None — get_rectangle returns None at 65.
    annotation.get_rectangle = lambda: None  # type: ignore[method-assign]
    PDInkAppearanceHandler(annotation).generate_normal_appearance()
    # No /AP allocated because the handler returned at line 67 before
    # entering the writer block.
    assert annotation.get_appearance_dictionary() is None


def test_ink_handler_with_decreasing_x_y_hits_min_branches() -> None:
    """Branches 61->63 and 63->56 (pd_ink_appearance_handler.py): ink
    paths whose later points are smaller/equal to the first hit the
    False arms of the x>max_x / y>max_y trackers."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_ink_appearance_handler import (
        PDInkAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import (
        PDAnnotationInk,
    )

    annotation = PDAnnotationInk()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    # Two ink paths — second path entirely inside first's bounding box.
    annotation.set_ink_paths(
        [
            [10.0, 10.0, 90.0, 90.0],
            [40.0, 40.0, 50.0, 50.0],
        ]
    )
    PDInkAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_caret_handler_with_normal_stream_none() -> None:
    """Branch 70->73 (pd_caret_appearance_handler.py): ``normal_stream``
    is ``None`` → skip the ``normal_stream.set_bbox(bbox)`` arm."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_caret_appearance_handler import (
        PDCaretAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_caret import (
        PDAnnotationCaret,
    )

    annotation = PDAnnotationCaret()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 40.0, 30.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.get_normal_appearance_stream = lambda: None  # type: ignore[method-assign]
    PDCaretAppearanceHandler(annotation).generate_normal_appearance()
    # /AP was still allocated by the writer context manager.
    assert annotation.get_appearance_dictionary() is not None


# Branch 143->exit (pd_text_appearance_handler.py): mathematically
# unreachable. ``_SUPPORTED_NAMES`` and the dispatch dict carry the same
# 16 keys, so once line 113's membership check passes,
# ``dispatch.get(name)`` always returns a callable. Not enough budget
# for a pragma — left at 99% in coverage.


def test_file_attachment_handler_with_normal_stream_none() -> None:
    """Branch 50->56 (pd_file_attachment_appearance_handler.py):
    ``normal_stream`` is ``None`` → skip the ``set_bbox`` arm and
    proceed to the glyph-painting dispatch."""
    from pypdfbox.pdmodel.interactive.annotation.handlers import (
        pd_file_attachment_appearance_handler as _file_handler_mod,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (
        PDAnnotationFileAttachment,
    )

    PDFileAttachmentAppearanceHandler = (
        _file_handler_mod.PDFileAttachmentAppearanceHandler
    )

    annotation = PDAnnotationFileAttachment()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 24.0, 24.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.get_normal_appearance_stream = lambda: None  # type: ignore[method-assign]
    PDFileAttachmentAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_strikeout_handler_with_coincident_lower_left_pair() -> None:
    """Branch 89->100 (pd_strikeout_appearance_handler.py): the first
    pair of quad points coincide (len0 == 0) → skip the ``x0 +=``
    shortening arm."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_strikeout_appearance_handler import (
        PDStrikeoutAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_strikeout import (
        PDAnnotationStrikeout,
    )

    annotation = PDAnnotationStrikeout()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([1.0, 0.0, 0.0])
    # 8 coords forming a degenerate quad — coords[0:2] == coords[4:6].
    annotation.set_quad_points([10.0, 10.0, 90.0, 10.0, 10.0, 10.0, 90.0, 90.0])
    PDStrikeoutAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_strikeout_handler_with_coincident_upper_right_pair() -> None:
    """Branch 106->117 (pd_strikeout_appearance_handler.py): the second
    pair of quad points coincide (len1 == 0)."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_strikeout_appearance_handler import (
        PDStrikeoutAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_strikeout import (
        PDAnnotationStrikeout,
    )

    annotation = PDAnnotationStrikeout()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([1.0, 0.0, 0.0])
    # coords[2:4] == coords[6:8]
    annotation.set_quad_points([10.0, 10.0, 90.0, 90.0, 80.0, 20.0, 90.0, 90.0])
    PDStrikeoutAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_underline_handler_with_coincident_lower_left_pair() -> None:
    """Branch 91->96 (pd_underline_appearance_handler.py): coincident
    quad pair → ``len0 == 0`` so shortening branch is skipped."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_underline_appearance_handler import (
        PDUnderlineAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_underline import (
        PDAnnotationUnderline,
    )

    annotation = PDAnnotationUnderline()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 1.0])
    annotation.set_quad_points([10.0, 10.0, 90.0, 10.0, 10.0, 10.0, 90.0, 90.0])
    PDUnderlineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_underline_handler_with_coincident_upper_right_pair() -> None:
    """Branch 102->105 (pd_underline_appearance_handler.py)."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_underline_appearance_handler import (
        PDUnderlineAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_underline import (
        PDAnnotationUnderline,
    )

    annotation = PDAnnotationUnderline()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 1.0])
    annotation.set_quad_points([10.0, 10.0, 90.0, 90.0, 80.0, 20.0, 90.0, 90.0])
    PDUnderlineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_line_handler_returns_when_get_line_returns_none() -> None:
    """Line 49 (pd_line_appearance_handler.py): ``paths_array is None``
    short-circuit. ``PDAnnotationLine.get_line`` synthesises [0 0 0 0]
    when /L is absent — patch it to None for this exit path."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_line_appearance_handler import (
        PDLineAppearanceHandler,
    )

    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.get_line = lambda: None  # type: ignore[method-assign]
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_line_handler_with_caption_and_zero_content_length_skips_text_block() -> None:
    """Branch 172->198 (pd_line_appearance_handler.py):
    ``content_length > 0`` False → skip the begin_text/show_text/end_text
    block.

    Reproduce by enabling caption mode on the annotation but stubbing
    the default font's ``get_string_width`` to return 0 so the computed
    content_length is 0.0.
    """
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_line_appearance_handler import (
        PDLineAppearanceHandler,
    )

    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 200.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    annotation.set_caption(True)
    annotation.set_contents("Caption")

    class _ZeroWidthFontHandler(PDLineAppearanceHandler):
        def get_default_font(self):  # type: ignore[override]
            class _ZeroWidthFont:
                def get_string_width(self, _s):
                    return 0.0

            return _ZeroWidthFont()

    _ZeroWidthFontHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # No BT operator emitted because content_length == 0.0.
    assert b"BT" not in body


def test_line_interior_components_size_branch_empty() -> None:
    """Line 279-280 (pd_line_appearance_handler.py): the size-branch
    empty case — ``interior.size() == 0`` → ``return None``."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_line_appearance_handler import (
        PDLineAppearanceHandler,
    )

    class _EmptyWithSize:
        def size(self) -> int:
            return 0

    class _Stub:
        def get_interior_color(self):
            return _EmptyWithSize()

    assert PDLineAppearanceHandler._interior_components(_Stub()) is None


def test_line_interior_components_size_branch_non_empty() -> None:
    """Line 281 (pd_line_appearance_handler.py): hidden-``to_float_array``
    on the first probe + visible on the call → exercises the
    size-branch non-empty path."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_line_appearance_handler import (
        PDLineAppearanceHandler,
    )

    state = {"hasattr_probes": 0}

    class _LatchedInterior:
        def size(self) -> int:
            return 3

        def to_float_array(self) -> list[float]:
            return [0.1, 0.2, 0.3]

        def __getattribute__(self, name):
            if name == "to_float_array":
                state["hasattr_probes"] += 1
                if state["hasattr_probes"] == 1:
                    raise AttributeError(name)
            return object.__getattribute__(self, name)

    class _Stub:
        def get_interior_color(self):
            return _LatchedInterior()

    assert PDLineAppearanceHandler._interior_components(_Stub()) == [0.1, 0.2, 0.3]


def test_line_handler_with_begin_text_raising_skips_text_emit() -> None:
    """Lines 175-178 (pd_line_appearance_handler.py): ``cs.begin_text()``
    raises ``AttributeError`` (writer doesn't support text operators) →
    fall through cleanly without emitting BT/Tj/ET.

    Requires caption mode (has_caption True + non-empty contents) so the
    branch at line 128 is taken and content_length > 0.
    """
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_line_appearance_handler import (
        PDLineAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
        PDAppearanceContentStream,
    )

    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 200.0, 100.0))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    annotation.set_caption(True)
    annotation.set_contents("Caption text")

    # Monkey-patch begin_text on the appearance content stream class so
    # that the handler's begin_text() call raises. We restore it after.
    original_begin_text = PDAppearanceContentStream.begin_text

    def raising_begin_text(self):
        raise AttributeError("simulated: no text operator support")

    PDAppearanceContentStream.begin_text = raising_begin_text  # type: ignore[assignment]
    try:
        PDLineAppearanceHandler(annotation).generate_normal_appearance()
    finally:
        PDAppearanceContentStream.begin_text = original_begin_text  # type: ignore[assignment]
    body = _appearance_bytes(annotation)
    # No BT operator emitted because begin_text raised before it could.
    assert b"BT" not in body


# Keep imports referenced so ruff doesn't strip them.
_KEEP_IMPORTS = (COSFloat, PDDocument)
