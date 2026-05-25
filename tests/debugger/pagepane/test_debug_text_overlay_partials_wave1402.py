"""Wave 1402 — branch-coverage round-out for
``DebugTextOverlay.calculate_glyph_bounds``.

Targets the residual partial branches in
``pypdfbox/debugger/pagepane/debug_text_overlay.py``:

* 535->539 — ``fm`` has fewer than 6 components ⇒ skip the matrix
  concatenation.
* 557->573 — font_bbox is ``None`` ⇒ skip the per-axis clamp loop.
* 592->591 — ``get_normalized_path`` yields an item that does not
  satisfy the (tuple, len 2, numeric[0]) gate ⇒ skip into the next
  iteration.
* 598->601 — collected points list is empty ⇒ stay on the bbox
  fallback path.
* 634->642 — stretch-needed gate True but font_width <= 0 or the
  width-delta is below the 1e-4 threshold ⇒ skip the scale step.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.debugger.pagepane.debug_text_overlay import calculate_glyph_bounds


class _Bbox:
    def __init__(
        self,
        llx: float = 0.0,
        lly: float = 0.0,
        urx: float = 100.0,
        ury: float = 100.0,
    ) -> None:
        self._llx, self._lly, self._urx, self._ury = llx, lly, urx, ury

    def get_lower_left_x(self) -> float:
        return self._llx

    def get_lower_left_y(self) -> float:
        return self._lly

    def get_upper_right_x(self) -> float:
        return self._urx

    def get_upper_right_y(self) -> float:
        return self._ury

    def set_lower_left_x(self, v: float) -> None:
        self._llx = v

    def set_lower_left_y(self, v: float) -> None:
        self._lly = v

    def set_upper_right_x(self, v: float) -> None:
        self._urx = v

    def set_upper_right_y(self, v: float) -> None:
        self._ury = v


class _NonVectorFont:
    """A vector-style (non-Type3) font with a tunable normalized-path
    and bbox getter."""

    def __init__(
        self,
        *,
        normalized_path: Any = None,
        bbox: _Bbox | None = None,
        font_matrix: tuple[float, ...] = (0.001, 0.0, 0.0, 0.001, 0.0, 0.0),
        embedded: bool = True,
        vertical: bool = False,
        standard14: bool = False,
        explicit_width: bool = False,
        width_from_font: float = 0.0,
    ) -> None:
        self._np = normalized_path
        self._bbox = bbox or _Bbox()
        self._fm = font_matrix
        self._embedded = embedded
        self._vertical = vertical
        self._standard14 = standard14
        self._explicit_width = explicit_width
        self._wff = width_from_font

    def get_font_matrix(self) -> tuple[float, ...]:
        return self._fm

    def get_bounding_box(self) -> _Bbox:
        return self._bbox

    def get_normalized_path(self, _code: int) -> Any:
        return self._np

    def is_embedded(self) -> bool:
        return self._embedded

    def is_vertical(self) -> bool:
        return self._vertical

    def is_standard14(self) -> bool:
        return self._standard14

    def has_explicit_width(self, _code: int) -> bool:
        return self._explicit_width

    def get_width_from_font(self, _code: int) -> float:
        return self._wff


_AT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def test_calculate_glyph_bounds_short_font_matrix() -> None:
    """535->539 — ``get_font_matrix`` returns a 4-tuple ⇒ ``len(fm) < 6``
    so the concatenation step is skipped but processing continues."""
    font = _NonVectorFont(font_matrix=(0.001, 0.0, 0.0, 0.001))
    result = calculate_glyph_bounds(_AT, font, code=0x20, displacement=None)
    # Should still produce a 4-corner bbox via the fallback path.
    assert result is not None
    assert len(result) == 4


def test_calculate_glyph_bounds_normalized_path_with_non_tuple_items() -> None:
    """592->591 — ``raw_path`` items don't pass the ``(tuple, len=2,
    numeric)`` gate ⇒ inner ``if`` is False and the loop continues.

    Combine with empty-pts to also drive 598->601 (no points collected
    ⇒ falls through to the bbox-based path)."""
    # All items fail the gate (one is a 3-tuple, one is a str).
    font = _NonVectorFont(normalized_path=[(1.0, 2.0, 3.0), "literal"])
    result = calculate_glyph_bounds(_AT, font, code=0x20, displacement=None)
    # The bbox fallback is reached and produces a 4-corner result.
    assert result is not None
    assert len(result) == 4


def test_calculate_glyph_bounds_stretch_with_zero_width_skips_scale() -> None:
    """634->642 — stretch_needed True (non-embedded, non-vertical,
    non-standard14, has explicit width) but ``get_width_from_font``
    returns 0 ⇒ the scaling-arm guard ``font_width > 0`` is False, so
    the at-matrix update is skipped."""

    class _Disp:
        def get_x(self) -> float:
            return 0.5

    font = _NonVectorFont(
        embedded=False,
        vertical=False,
        standard14=False,
        explicit_width=True,
        width_from_font=0.0,  # ⇒ font_width == 0 ⇒ skip scale
    )
    result = calculate_glyph_bounds(_AT, font, code=0x20, displacement=_Disp())
    assert result is not None


def test_calculate_glyph_bounds_type3_with_no_font_bbox() -> None:
    """557->573 — Type3 path: ``font_bbox`` is ``None`` ⇒ the per-axis
    clamp loop is skipped."""
    from pypdfbox.cos import COSDictionary, COSName, COSStream
    from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

    # Build a minimal Type3 font with /CharProcs + /Resources.
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type3"))
    char_procs = COSDictionary()
    cp_stream = COSStream()
    # d1 operator declares both width AND bounding box → glyph_bbox
    # resolves to a real PDRectangle rather than None.
    cp_stream.set_data(b"500 0 0 0 100 100 d1\n")
    char_procs.set_item("a", cp_stream)
    d.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    encoding = COSDictionary()
    encoding.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    # Differences: [97 /a]
    from pypdfbox.cos import COSArray, COSInteger

    diffs = COSArray()
    diffs.add(COSInteger.get(97))
    diffs.add(COSName.get_pdf_name("a"))
    encoding.set_item(COSName.get_pdf_name("Differences"), diffs)
    d.set_item(COSName.get_pdf_name("Encoding"), encoding)
    d.set_item(
        COSName.get_pdf_name("FontMatrix"),
        _make_array_floats(0.001, 0.0, 0.0, 0.001, 0.0, 0.0),
    )
    d.set_item(
        COSName.get_pdf_name("FontBBox"),
        _make_array_floats(0.0, 0.0, 100.0, 100.0),
    )
    d.set_item(
        COSName.get_pdf_name("Widths"),
        _make_array_floats(500.0),
    )
    d.set_item(COSName.get_pdf_name("FirstChar"), COSInteger.get(97))
    d.set_item(COSName.get_pdf_name("LastChar"), COSInteger.get(97))

    font = PDType3Font(d)
    # Monkey-patch get_bounding_box to return None so the clamp loop
    # at 557 is skipped. Result may be None when the upstream Type3
    # bbox machinery returns None — we only care that we exercised the
    # 557->573 branch.
    font.get_bounding_box = lambda: None  # type: ignore[method-assign]
    calculate_glyph_bounds(_AT, font, code=97, displacement=None)


def _make_array_floats(*vals: float) -> Any:
    from pypdfbox.cos import COSArray, COSFloat

    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(v))
    return arr
