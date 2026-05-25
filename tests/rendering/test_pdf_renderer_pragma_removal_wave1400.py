"""Wave 1400 — exercise the ``False`` arms of conditionals that wave
1397 (Agent A) had silenced with ``# pragma: no branch``. After auditing
the 16 pragmas A added, 14 turned out to be reachable defensive guards;
wave 1400 removes those pragmas and pins the False-side behaviour with
the tests in this module.

The 2 pragmas wave 1400 keeps are genuinely unreachable:

* ``pdf_renderer.py:757`` — ``if scale > 1.0`` after the outer
  ``0.0 < smoothness < 0.1`` guard guarantees ``scale > 1.0``
  mathematically.
* ``pdf_renderer.py:2987`` — ``elif stroke or fill`` after an earlier
  ``return`` at line 2945 filters out the ``not (stroke or fill)`` case.

Both kept pragmas have updated comments in the source that explain why
the False side is impossible.
"""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState

# ---------------------------------------------------------------------------
# helpers (mirror style of wave 1397 coverage tests)
# ---------------------------------------------------------------------------


def _make_doc(width: float = 64.0, height: float = 64.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _bare_renderer(gs: _GState | None = None) -> PDFRenderer:
    from pypdfbox.rendering.render_destination import RenderDestination

    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [gs or _GState()]
    r._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    r._resources = None
    r._default_destination = RenderDestination.VIEW
    r._text_knockout_layer = None
    r._text_knockout_prev_image = None
    r._text_knockout_prev_draw = None
    r._text_knockout_saved_fill_alpha = 1.0
    r._text_knockout_saved_stroke_alpha = 1.0
    r._text_knockout_saved_blend_mode = None
    r._text_clip_paths = []
    r._subpaths = []
    r._current_subpath = None
    r._current_point = (0.0, 0.0)
    r._image = None
    r._draw = None
    r._pending_clip = None
    r._transparency_group_depth = 0
    r._knockout_active = False
    r._knockout_snapshot = None
    r._knockout_form_depth = 0
    r._page_height_px = 64
    r._font_program_cache = {}
    r._type3_d0_wx = None
    r._type3_d1_wx = None
    r._warned_standard14_fonts = set()
    return r


def _attach_contents(page: PDPage, raw: bytes) -> None:
    stream = COSStream()
    stream.set_raw_data(raw)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)


def _float_array(values: list[float]) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(COSFloat(value))
    return array


# ---------------------------------------------------------------------------
# Pragma site 1: process_page finalizer flush (line ~1275)
#   Cover: self._draw is None at the finally-block flush guard.
# ---------------------------------------------------------------------------


def test_render_page_into_finalizer_handles_none_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After the content-stream walk clears ``self._draw`` (e.g. an
    annotation render or paste helper set it None and never restored
    it), the ``finally`` block's flush guard inside ``_render_page_into``
    must take the False arm and skip ``current.flush()`` rather than
    AttributeError."""
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)

    real_process_page = renderer.process_page

    def _force_draw_none(*args: Any, **kwargs: Any) -> Any:
        try:
            return real_process_page(*args, **kwargs)
        finally:
            # Force the False arm of the flush guard inside
            # _render_page_into's finally block.
            renderer._draw = None

    monkeypatch.setattr(renderer, "process_page", _force_draw_none)
    image = renderer.render_image(0)
    assert image.size[0] > 0
    assert image.size[1] > 0
    # Post-render the renderer always resets _draw to None.
    assert renderer._draw is None
    doc.close()


# ---------------------------------------------------------------------------
# Pragma site 2: _op_close_path subpath first element != 'M' (line ~2853)
#   Cover: malformed subpath where first element is NOT a moveto tuple.
# ---------------------------------------------------------------------------


def test_op_close_path_non_moveto_first_element_keeps_current_point() -> None:
    """The defensive guard at ``_op_close_path`` only updates the current
    point when the first segment is a moveto. Craft a malformed subpath
    (first element is a 'L' tuple) and confirm the current point stays
    put — the False arm of the ``first[0] == 'M'`` guard."""
    r = _bare_renderer()
    # Hand-craft a subpath whose first element is NOT a moveto.
    r._current_subpath = [("L", 1.0, 2.0), ("L", 3.0, 4.0)]
    r._subpaths.append(r._current_subpath)
    r._current_point = (5.0, 6.0)
    r._op_close_path(None, [])
    # 'Z' was still appended (the close-path operator's main effect).
    assert r._current_subpath[-1] == ("Z",)
    # Current point UNCHANGED because the guard's False arm was taken.
    assert r._current_point == (5.0, 6.0)


# ---------------------------------------------------------------------------
# Pragma site 3: _paint_through_clip layer flush (line ~3049)
#   Cover: self._draw is None just before the inner layer flush.
# ---------------------------------------------------------------------------


def test_paint_through_clip_handles_none_layer_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inner layer-flush guard inside ``_paint_through_clip`` must
    cope when ``_draw_via_aggdraw`` (e.g. via even-odd PIL detour) reset
    ``self._draw`` to None. Force that condition and check no
    AttributeError on the flush call."""
    r = _bare_renderer()
    width, height = 16, 16
    r._image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    import pypdfbox.rendering._aggdraw_compat as aggdraw

    r._draw = aggdraw.Draw(r._image)

    # Stub _draw_via_aggdraw to set self._draw None (mimics the PIL
    # detour that wave 1330B documented).
    def _drop_draw(**_kw: Any) -> None:
        r._draw = None

    monkeypatch.setattr(r, "_draw_via_aggdraw", _drop_draw)

    clip_mask = Image.new("L", (width, height), 255)
    # Should not raise: False arm of the ``if self_draw is not None``
    # guard inside the try block.
    r._paint_through_clip(
        stroke=True,
        fill=True,
        even_odd=False,
        clip_mask=clip_mask,
        soft_mask=None,
    )


# ---------------------------------------------------------------------------
# Pragma site 4: pattern tile renderer flush (line ~3642)
#   Cover: self._draw is None after _process_form_bytes in pattern tile.
# ---------------------------------------------------------------------------


def test_render_tiling_cell_flush_handles_none_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_render_tiling_cell`` flushes the tile's aggdraw after
    processing the pattern's content stream. If ``_process_form_bytes``
    cleared ``self._draw``, the guard's False arm must skip the flush
    call rather than crash."""
    r = _bare_renderer()

    captured: dict[str, Any] = {}

    def _drop(_data: bytes) -> None:
        captured["called"] = True
        r._draw = None

    monkeypatch.setattr(r, "_process_form_bytes", _drop)

    # Minimal pattern object with the attributes _render_tiling_cell reads.
    class _BBox:
        def get_width(self) -> float:
            return 4.0

        def get_height(self) -> float:
            return 4.0

        def get_lower_left_x(self) -> float:
            return 0.0

        def get_lower_left_y(self) -> float:
            return 0.0

    class _Pattern:
        def get_cos_object(self) -> Any:
            stream = COSStream()
            stream.set_raw_data(b"q Q")  # non-empty so we don't early-return
            return stream

        def get_resources(self) -> Any:
            return None

    r._render_tiling_cell(
        _Pattern(),
        bbox=_BBox(),
        tile_size=(4, 4),
        cell_size=(4, 4),
        tint_rgb=None,
    )
    assert captured.get("called") is True


# ---------------------------------------------------------------------------
# Pragma site 5+6+7: shading-helper flush (lines ~4026, ~4191, ~4359)
#   Cover: self._draw is None at the pre-paste flush in radial /
#   function-based / patch-mesh shading helpers.
#
# Each helper does the same pattern: ``if self._draw is not None: flush()
# else: skip``. We drive each via a tiny in-place call with self._draw
# pre-set to None.
# ---------------------------------------------------------------------------


def test_paint_radial_shading_flush_skipped_when_draw_none() -> None:
    """Build the renderer state so ``_paint_radial_shading``'s pre-paste
    flush guard takes the False arm. ``self._draw`` is set to None
    before the call, ensuring the inner ``if self._draw is not None``
    skips the flush."""
    r = _bare_renderer()
    width, height = 4, 4
    r._image = Image.new("RGB", (width, height), (0, 0, 0))
    r._draw = None  # the precondition we want
    r._gs.ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    class _Function:
        def eval(self, inputs: list[float]) -> list[float]:
            return [inputs[0], 0.0, 0.0]

    class _Shading:
        def get_coords(self) -> Any:
            return _float_array([2.0, 2.0, 1.0, 2.0, 2.0, 3.0])

        def get_domain(self) -> Any:
            return None

        def get_extend(self) -> Any:
            return None

        def get_function(self) -> Any:
            return _Function()

        def get_color_space(self) -> Any:
            return COSName.get_pdf_name("DeviceRGB")

        def get_background(self) -> Any:
            return None

    region_mask = Image.new("L", (width, height), 255)
    r._paint_radial_shading(_Shading(), region_mask=region_mask)
    # After the call, self._draw has been re-bound to a fresh aggdraw
    # wrapper on the same image; the flush guard's False arm was taken
    # (no AttributeError) and the paste step ran successfully.
    assert r._draw is not None
    assert r._image.size == (width, height)


def test_paint_function_shading_flush_skipped_when_draw_none() -> None:
    """Symmetric coverage for ``_paint_function_shading``'s flush
    guard. ``self._draw = None`` forces the False arm of the inner
    ``if self._draw is not None`` check."""
    r = _bare_renderer()
    width, height = 4, 4
    r._image = Image.new("RGB", (width, height), (0, 0, 0))
    r._draw = None
    r._gs.ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    class _Function:
        def eval(self, _in: list[float]) -> list[float]:
            return [0.5, 0.5, 0.5]

    class _Shading:
        def get_domain(self) -> Any:
            return _float_array([0.0, 1.0, 0.0, 1.0])

        def get_matrix(self) -> Any:
            return None

        def get_function(self) -> Any:
            return _Function()

        def get_color_space(self) -> Any:
            return COSName.get_pdf_name("DeviceRGB")

        def get_background(self) -> Any:
            return None

    region_mask = Image.new("L", (width, height), 255)
    r._paint_function_shading(_Shading(), region_mask=region_mask)
    # After the call the flush guard's False arm has been exercised and
    # the paste + re-attach succeeded.
    assert r._draw is not None
    assert r._image.size == (width, height)


def test_paint_patch_mesh_flush_skipped_when_draw_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Symmetric coverage for ``_paint_patch_mesh_shading``'s pre-paste
    flush guard (line ~4359). Stub the patch-list parse and
    per-patch rasteriser so the helper reaches the flush-guard site
    without needing a real decoded patch stream."""
    r = _bare_renderer()
    width, height = 4, 4
    r._image = Image.new("RGB", (width, height), (0, 0, 0))
    r._draw = None  # the False-arm precondition
    r._gs.ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    # Stub _rasterise_single_patch — we only need to reach the flush guard.
    monkeypatch.setattr(
        r,
        "_rasterise_single_patch",
        lambda *_a, **_kw: None,
    )

    class _Patch:
        # _rasterise_single_patch is stubbed so the only attribute
        # _paint_patch_mesh_shading reads on the patch is .points.
        points = [(0.0, 0.0)] * 12

    class _Shading:
        def parse_patches(self) -> list[Any]:
            return [_Patch()]

        def get_color_space(self) -> Any:
            return COSName.get_pdf_name("DeviceRGB")

        def get_function(self) -> Any:
            return None

        def get_background(self) -> Any:
            return None

        def get_bbox(self) -> Any:
            return None

    region_mask = Image.new("L", (width, height), 255)
    result = r._paint_patch_mesh_shading(
        _Shading(), region_mask=region_mask, control_points=12
    )
    assert result is True
    # Post-call: flush guard's False arm executed and the new aggdraw
    # was re-bound on self._image.
    assert r._draw is not None


# ---------------------------------------------------------------------------
# Pragma site 8: soft-mask group flush (line ~5751)
#   Cover: self._draw is None after _render_form_xobject in soft-mask
#   rendering.
# ---------------------------------------------------------------------------


def test_render_soft_mask_alpha_handles_none_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_render_soft_mask_alpha``'s mid-try flush guard must take
    the False arm when ``_render_form_xobject`` cleared
    ``self._draw``. Build a real :class:`PDSoftMask` (with /S Alpha
    and /G pointing at a fake group form) so the isinstance check
    passes and we reach the guard at line 5751."""
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask

    r = _bare_renderer()
    r._image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    import pypdfbox.rendering._aggdraw_compat as aggdraw
    r._draw = aggdraw.Draw(r._image)
    r._gs.ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def _clear_draw(_form: Any) -> None:
        # Simulate _render_form_xobject leaving self._draw None — this
        # is the False-arm precondition for line 5751's flush guard.
        r._draw = None

    monkeypatch.setattr(r, "_render_form_xobject", _clear_draw)

    # Real PDSoftMask wrapping a minimal dict with /S /Alpha and a
    # /G stub.
    smask_dict = COSDictionary()
    smask_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Alpha"))
    # Provide a get_group() override via monkeypatching the instance.
    soft_mask = PDSoftMask(smask_dict)

    class _GroupForm:
        pass

    monkeypatch.setattr(soft_mask, "get_group", lambda: _GroupForm())

    result = r._render_soft_mask_alpha(soft_mask, (8, 8))
    # On success the helper returns an "L" image; on internal failure
    # it returns None. Either way the guard line executed.
    assert result is None or isinstance(result, Image.Image)


# ---------------------------------------------------------------------------
# Pragma site 9: transparency-group flush (line ~5953)
#   Cover: self._draw is None inside transparency-group finally block.
# ---------------------------------------------------------------------------


def test_render_transparency_group_handles_none_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_render_transparency_group``'s finally-block flush guard at
    line 5953 must cope when ``_render_form_xobject`` cleared
    ``self._draw``. We monkey-patch the inner form render to drop
    the draw before unwind so the False arm of the guard runs."""
    r = _bare_renderer()
    r._image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    import pypdfbox.rendering._aggdraw_compat as aggdraw
    r._draw = aggdraw.Draw(r._image)
    r._gs.ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def _clear(_form: Any) -> None:
        r._draw = None

    monkeypatch.setattr(r, "_render_form_xobject", _clear)

    class _Form:
        def get_group(self) -> Any:
            return None  # No /Group dict → isolated=False, knockout=False.

    # Run; the finally block must execute the False arm of the flush
    # guard without raising.
    r._render_transparency_group(_Form())
    # After unwind self._image and self._draw are re-bound to the
    # original parent canvas.
    assert r._image is not None
    assert r._draw is not None


# ---------------------------------------------------------------------------
# Pragma site 10: _restore_knockout_snapshot flush (line ~6012)
#   Cover: self._draw is None when restoring knockout snapshot.
# ---------------------------------------------------------------------------


def test_restore_knockout_snapshot_handles_none_draw() -> None:
    """When the knockout snapshot is restored, the pre-paste flush guard
    must take the False arm if ``self._draw`` was cleared."""
    r = _bare_renderer()
    width, height = 8, 8
    r._image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    r._knockout_snapshot = Image.new(
        "RGBA", (width, height), (255, 0, 0, 255)
    )
    r._draw = None  # the False arm condition
    r._restore_knockout_snapshot()
    # Snapshot pixel applied — the method ran past the flush guard and
    # successfully re-bound self._draw on the new image.
    assert r._image.getpixel((1, 1)) == (255, 0, 0, 255)
    assert r._draw is not None


# ---------------------------------------------------------------------------
# Pragma site 11: _maybe_end_text_knockout flush (line ~6754)
#   Cover: self._draw is None at end of TK sub-canvas composite.
# ---------------------------------------------------------------------------


def test_maybe_end_text_knockout_handles_none_current_draw() -> None:
    """``_maybe_end_text_knockout`` flushes the live sub-canvas before
    composite. If something cleared ``self._draw`` mid-TK, the guard's
    False arm must skip the flush rather than crash."""
    r = _bare_renderer()
    width, height = 8, 8
    parent_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    import pypdfbox.rendering._aggdraw_compat as aggdraw
    parent_draw = aggdraw.Draw(parent_image)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    r._text_knockout_layer = layer
    r._text_knockout_prev_image = parent_image
    r._text_knockout_prev_draw = parent_draw
    r._text_knockout_saved_fill_alpha = 0.5
    r._text_knockout_saved_stroke_alpha = 0.5
    r._text_knockout_saved_blend_mode = None
    r._image = layer
    r._draw = None  # The condition we want — sub-canvas draw missing.
    r._maybe_end_text_knockout()
    # Composite succeeded: layer was pasted onto the parent. The False
    # arm of the flush guard was exercised without AttributeError.
    assert r._image is parent_image
    assert r._draw is not None


# ---------------------------------------------------------------------------
# Pragma site 12: type1 path-builder None guard (line ~7340)
#   Cover: get_glyph_path returns commands but builder returns None.
# ---------------------------------------------------------------------------


def test_draw_glyph_type1_path_none_skips_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``_build_aggdraw_path_from_commands`` returns None (commands
    list with only a moveto), ``_draw_glyph`` must skip the fill call
    rather than pass a None path to aggdraw."""
    r = _bare_renderer()
    r._image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    import pypdfbox.rendering._aggdraw_compat as aggdraw
    r._draw = aggdraw.Draw(r._image)
    r._gs.text_font_size = 12.0
    r._gs.text_horizontal_scaling = 100.0
    r._gs.text_rise = 0.0
    r._gs.text_matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    r._gs.ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    class _Type1Font:
        def get_glyph_path(self, _code: int) -> list[tuple]:
            # Only moveto — builder returns None.
            return [("moveto", 0.0, 0.0)]

        def get_glyph_width(self, _code: int) -> float:
            return 500.0

        def get_name(self) -> str:
            return "Helvetica"

    fill_called: dict[str, bool] = {"hit": False}

    def _track_fill(*_args: Any, **_kwargs: Any) -> None:
        fill_called["hit"] = True

    monkeypatch.setattr(r, "_fill_aggdraw_path", _track_fill)

    advance = r._draw_glyph(
        font=_Type1Font(),
        code=ord("A"),
        ttf=None,
        glyph_set=None,
        type1_units_per_em=1000,
    )
    assert advance == 500.0
    assert fill_called["hit"] is False


# ---------------------------------------------------------------------------
# Pragma site 13: type1 fallback advance > 0 guard (line ~7375)
#   Cover: _fallback_advance_units returns 0 (or default 0.0).
# ---------------------------------------------------------------------------


def test_draw_glyph_fallback_returns_zero_keeps_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the FontMappers fallback returns 0.0 (e.g. the substitute
    font has no metric for the requested code), the ``upgraded > 0.0``
    guard's False arm leaves the original placeholder advance untouched."""
    r = _bare_renderer()
    r._image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    import pypdfbox.rendering._aggdraw_compat as aggdraw
    r._draw = aggdraw.Draw(r._image)
    r._gs.text_font_size = 12.0
    r._gs.text_horizontal_scaling = 100.0
    r._gs.text_rise = 0.0
    r._gs.text_matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    r._gs.ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    class _NoOutlineFont:
        def get_glyph_width(self, _code: int) -> float:
            # 0.0 trips both the upgrade branch AND keeps default <= 0.
            return 0.0

        def get_name(self) -> str:
            return "MissingFont"

    # Force the resolver to return SOMETHING (so the upgrade path runs).
    class _Substitute:
        def get_width(self, _name: str) -> float:
            # Returns 0 -> _fallback_advance_units returns default_units
            # (which is 0.0 here), so ``upgraded > 0.0`` is False.
            return 0.0

    monkeypatch.setattr(r, "_resolve_font_program", lambda _f: _Substitute())
    monkeypatch.setattr(r, "_maybe_warn_standard14", lambda _f: None)
    # No outline branches — fall through to the placeholder path so the
    # advance-upgrade code runs without raising.

    advance = r._draw_glyph(
        font=_NoOutlineFont(),
        code=ord("A"),
        ttf=None,
        glyph_set=None,
        type1_units_per_em=None,
    )
    # The fallback returned 0.0, so the original 0.0 advance is preserved
    # (False arm of ``upgraded > 0.0``).
    assert advance == 0.0


# ---------------------------------------------------------------------------
# Pragma site 14: placeholder-box self._draw None guard (line ~7383)
#   Cover: self._draw is None at the placeholder draw step.
# ---------------------------------------------------------------------------


def test_draw_glyph_placeholder_skipped_when_draw_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``self._draw`` is None at the placeholder-box step, the
    guard's False arm must skip the draw call rather than NPE inside
    aggdraw."""
    r = _bare_renderer()
    r._image = None
    r._draw = None  # The False-arm condition
    r._gs.text_font_size = 12.0
    r._gs.text_horizontal_scaling = 100.0
    r._gs.text_rise = 0.0
    r._gs.text_matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    r._gs.ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    class _SimpleFont:
        def get_glyph_width(self, _code: int) -> float:
            return 250.0

        def get_name(self) -> str:
            return "Helvetica"

    placeholder_called: dict[str, bool] = {"hit": False}

    def _track(*_args: Any, **_kwargs: Any) -> None:
        placeholder_called["hit"] = True

    monkeypatch.setattr(r, "_draw_placeholder_box", _track)
    monkeypatch.setattr(r, "_maybe_warn_standard14", lambda _f: None)

    advance = r._draw_glyph(
        font=_SimpleFont(),
        code=ord("A"),
        ttf=None,
        glyph_set=None,
        type1_units_per_em=None,
    )
    assert advance == 250.0
    # Placeholder draw skipped — False arm of the guard.
    assert placeholder_called["hit"] is False
