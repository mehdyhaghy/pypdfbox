"""Wave 1348 coverage-boost tests for the debug-text overlay.

Targets the residual ``calculate_glyph_bounds`` exception arms:

  * Type3 ``get_char_proc`` raising → returns None (lines 544-545).
  * Type3 ``get_glyph_bbox`` raising → returns None (lines 551-552).
  * Type3 bbox-clamp setters raising → silently caught (lines 571-572).
  * Non-Type3 ``get_normalized_path`` raising → falls back to bbox
    (lines 584-585).
  * Non-Type3 bbox point construction raising → returns None
    (lines 615-616).
"""
from __future__ import annotations

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_name import COSName
from pypdfbox.debugger.pagepane.debug_text_overlay import calculate_glyph_bounds
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_IDENTITY_AT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _make_type3_font(font_bbox: PDRectangle | None = None) -> PDType3Font:
    """Construct a minimally valid PDType3Font wrapper."""
    font_dict = COSDictionary()
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type3"))
    if font_bbox is not None:
        font_dict.set_item(
            COSName.get_pdf_name("FontBBox"), font_bbox.to_cos_array()
        )
    font_dict.set_item(
        COSName.get_pdf_name("FontMatrix"),
        COSArray([
            COSFloat(0.01), COSFloat(0.0),
            COSFloat(0.0), COSFloat(0.01),
            COSFloat(0.0), COSFloat(0.0),
        ]),
    )
    return PDType3Font(font_dict)


# ---------------------------------------------------------------- Type3 paths


def test_calculate_glyph_bounds_type3_char_proc_raises_returns_none() -> None:
    """When ``get_char_proc`` raises (AttributeError / TypeError /
    ValueError), the helper returns ``None`` (lines 544-545)."""
    font = _make_type3_font(PDRectangle(0.0, 0.0, 100.0, 100.0))

    def _boom(_code: int):
        raise ValueError("char-proc lookup blew up")

    font.get_char_proc = _boom  # type: ignore[assignment]
    assert calculate_glyph_bounds(_IDENTITY_AT, font, 65, None) is None


def test_calculate_glyph_bounds_type3_get_glyph_bbox_raises_returns_none() -> None:
    """A ``CharProc`` whose ``get_glyph_bbox`` raises causes the helper to
    return ``None`` (lines 551-552)."""
    font = _make_type3_font(PDRectangle(0.0, 0.0, 100.0, 100.0))

    class _ExplodingProc:
        def get_glyph_bbox(self) -> PDRectangle:
            raise OSError("bbox unavailable")

    font.get_char_proc = lambda _code: _ExplodingProc()  # type: ignore[assignment]
    assert calculate_glyph_bounds(_IDENTITY_AT, font, 65, None) is None


def test_calculate_glyph_bounds_type3_bbox_clamp_setter_errors_swallowed() -> None:
    """A glyph bbox whose ``set_lower_left_x``/etc raise ``ValueError`` is
    silently caught and the (un-clamped) bbox still produces points
    (lines 571-572)."""
    font = _make_type3_font(PDRectangle(0.0, 0.0, 100.0, 100.0))

    class _ReadOnlyBBox(PDRectangle):
        def set_lower_left_x(self, _v: float) -> None:  # type: ignore[override]
            raise ValueError("read-only")

    class _CharProc:
        def __init__(self) -> None:
            self._bbox = _ReadOnlyBBox(10.0, 10.0, 50.0, 80.0)

        def get_glyph_bbox(self) -> _ReadOnlyBBox:
            return self._bbox

    font.get_char_proc = lambda _code: _CharProc()  # type: ignore[assignment]
    pts = calculate_glyph_bounds(_IDENTITY_AT, font, 65, None)
    # Even though clamp failed, points were still produced from the
    # original (un-clamped) bbox.
    assert pts is not None
    assert len(pts) == 4


# ------------------------------------------------------------ non-Type3 paths


class _StubBBox:
    """Minimal PDRectangle-shape duck."""

    def __init__(
        self,
        llx: float = -100.0,
        lly: float = -200.0,
        urx: float = 900.0,
        ury: float = 800.0,
    ) -> None:
        self.llx, self.lly, self.urx, self.ury = llx, lly, urx, ury

    def get_lower_left_x(self) -> float:
        return self.llx

    def get_lower_left_y(self) -> float:
        return self.lly

    def get_upper_right_x(self) -> float:
        return self.urx

    def get_upper_right_y(self) -> float:
        return self.ury


class _NonType3StubFont:
    """Non-Type3 font stub with the surface ``calculate_glyph_bounds`` needs."""

    def __init__(
        self,
        bbox: _StubBBox | None,
        *,
        normalized_path_fn=None,
    ) -> None:
        self._bbox = bbox
        self._normalized_path_fn = normalized_path_fn

    def get_bounding_box(self) -> _StubBBox | None:
        return self._bbox

    def get_font_matrix(self) -> list[float]:
        return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    def is_embedded(self) -> bool:
        return True

    def is_vertical(self) -> bool:
        return False

    def is_standard14(self) -> bool:
        return False

    def has_explicit_width(self, _code: int) -> bool:
        return False

    # Conditionally expose ``get_normalized_path`` so the ``getattr``
    # callable check inside calculate_glyph_bounds still triggers.
    def get_normalized_path(self, code: int):  # noqa: D401 - duck method
        if self._normalized_path_fn is None:
            return None
        return self._normalized_path_fn(code)


def test_calculate_glyph_bounds_get_normalized_path_raises_falls_back_to_bbox() -> None:
    """When ``get_normalized_path`` raises (TypeError / ValueError / OSError),
    the helper falls back to ``get_bounding_box`` (lines 584-585)."""

    def _boom(_code: int):
        raise TypeError("no path")

    font = _NonType3StubFont(_StubBBox(0.0, 0.0, 1000.0, 1000.0), normalized_path_fn=_boom)
    pts = calculate_glyph_bounds(_IDENTITY_AT, font, 65, None)
    assert pts is not None
    assert len(pts) == 4


def test_calculate_glyph_bounds_bbox_point_construction_raises_returns_none() -> None:
    """When the bbox accessors raise on the corner-construction step
    (``get_lower_left_x`` etc.), the helper returns ``None`` (lines
    615-616)."""

    class _PointsBoomBBox(_StubBBox):
        # Used by the corner-construction block.
        def get_lower_left_x(self) -> float:
            raise ValueError("bbox accessor broken")

    font = _NonType3StubFont(_PointsBoomBBox(), normalized_path_fn=lambda _c: None)
    assert calculate_glyph_bounds(_IDENTITY_AT, font, 65, None) is None
