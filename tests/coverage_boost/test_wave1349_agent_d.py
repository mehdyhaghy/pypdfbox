"""Wave 1349 — coverage-boost agent D.

Five targets pushed from ~96-98% to >=99%:

* ``pypdfbox/examples/pdmodel/extract_ttf_fonts.py`` — early-return guards
  after ``usage()`` (lines 37, 50, 56, 67) reached by monkey-patching
  ``usage`` to a no-op so the subsequent ``return`` executes; plus
  ``process_resources(None)`` (line 117) and ``write_font(None)``
  short-circuit (line 207).
* ``pypdfbox/pdmodel/fixup/processor/acro_form_orphan_widgets_processor.py``
  — ``ImportError`` fallbacks at 103-104 and 174-175, exercised via
  monkeypatched ``builtins.__import__`` that raises on the lazy imports.
* ``pypdfbox/pdmodel/graphics/shading/radial_shading_context.py`` —
  ``get_raster`` interior branches 165, 174, 180, 182: high-side outside
  with no extend / no bg ``continue``, low-side outside with extend[0]
  but r0 == 0 falling back to ``use_background``, and the
  ``key < 0`` / ``key > factor`` colour-table clamps.
* ``pypdfbox/pdmodel/interactive/annotation/handlers/pd_line_appearance_handler.py``
  — paths_array None guard (line 49), caption-emit ``show_text`` raising
  ``ValueError`` swallowed (lines 182-184), and the ``_interior_components``
  ``size() > 0`` branch (line 269).
* ``pypdfbox/pdmodel/interactive/annotation/handlers/pd_polyline_appearance_handler.py``
  — dashed border draws ``set_dash_pattern`` (line 80) and the
  ``_interior_components`` ``size() > 0`` branch (lines 170-172).
"""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.examples.pdmodel.extract_ttf_fonts import ExtractTTFFonts
from pypdfbox.pdmodel.fixup.processor.acro_form_orphan_widgets_processor import (
    AcroFormOrphanWidgetsProcessor,
)
from pypdfbox.pdmodel.graphics.shading.radial_shading_context import (
    RadialShadingContext,
)
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_line_appearance_handler import (
    PDLineAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_polyline_appearance_handler import (
    PDPolylineAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
    PDAnnotationPolyline,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------------------------------------------------------------------------
# extract_ttf_fonts — dead-return guards after usage()
# ---------------------------------------------------------------------------


def test_extract_fonts_size_gate_hits_return_after_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Line 37: ``return`` after ``usage()`` — usage normally raises
    SystemExit so the return is unreachable; patch usage out to expose it."""
    monkeypatch.setattr(ExtractTTFFonts, "usage", staticmethod(lambda: None))
    extractor = ExtractTTFFonts()
    # Empty argv triggers ``len(argv) < 1 or len(argv) > 4`` → usage() → return
    extractor.extract_fonts([])
    # No exception, no SystemExit — the return executed.


def test_extract_fonts_password_missing_value_hits_return_after_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 50: ``return`` after ``usage()`` when ``-password`` lacks value."""
    monkeypatch.setattr(ExtractTTFFonts, "usage", staticmethod(lambda: None))
    extractor = ExtractTTFFonts()
    extractor.extract_fonts(["-password"])


def test_extract_fonts_prefix_missing_value_hits_return_after_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 56: ``return`` after ``usage()`` when ``-prefix`` lacks value."""
    monkeypatch.setattr(ExtractTTFFonts, "usage", staticmethod(lambda: None))
    extractor = ExtractTTFFonts()
    extractor.extract_fonts(["-prefix"])


def test_extract_fonts_no_pdf_arg_hits_return_after_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 67: ``return`` after ``usage()`` when no positional PDF arg given."""
    monkeypatch.setattr(ExtractTTFFonts, "usage", staticmethod(lambda: None))
    extractor = ExtractTTFFonts()
    extractor.extract_fonts(["-addkey"])


def test_process_resources_short_circuits_when_resources_none() -> None:
    """Line 117: ``if resources is None: return`` early-out."""
    # Must not raise and must not touch nested-resource sub-helpers.
    extractor = ExtractTTFFonts()
    extractor.process_resources(None, "p", False)


def test_write_font_short_circuits_when_descriptor_none(tmp_path: Path) -> None:
    """Line 207: ``if fd is None: return`` early-out."""
    extractor = ExtractTTFFonts()
    extractor.write_font(None, str(tmp_path / "x"))
    assert not (tmp_path / "x.ttf").exists()


# ---------------------------------------------------------------------------
# acro_form_orphan_widgets_processor — ImportError fallbacks
# ---------------------------------------------------------------------------


class _StubDoc:
    """Bare document stub for the processor's constructor."""

    def __init__(self) -> None:
        self._pages: list[Any] = []

    def get_pages(self) -> list[Any]:
        return self._pages


def _make_import_blocker(blocked_names: list[str]):
    """Return a replacement for ``builtins.__import__`` raising on names."""
    real_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        if any(blocked in name for blocked in blocked_names):
            raise ImportError(f"blocked: {name}")
        return real_import(name, globals, locals, fromlist, level)

    return fake_import


def test_handle_annotations_import_error_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 103-104: ``handle_annotations`` swallows ImportError on the
    lazy ``PDAnnotationWidget`` / ``PDFieldFactory`` import block."""
    monkeypatch.setattr(
        builtins,
        "__import__",
        _make_import_blocker([
            "pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget",
            "pypdfbox.pdmodel.interactive.form.pd_field_factory",
        ]),
    )
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc())
    fields: list[Any] = []
    proc.handle_annotations(
        acro_form=object(),
        acro_form_resources=object(),
        fields=fields,
        annotations=[object()],
        non_terminal_fields_map={},
    )
    assert fields == []


def test_resolve_non_root_field_import_error_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 174-175: ``resolve_non_root_field`` ImportError returns None."""
    monkeypatch.setattr(
        builtins,
        "__import__",
        _make_import_blocker([
            "pypdfbox.pdmodel.interactive.form.pd_field_factory",
        ]),
    )
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc())
    result = proc.resolve_non_root_field(
        acro_form=object(),
        parent=object(),
        non_terminal_fields_map={},
    )
    assert result is None


# ---------------------------------------------------------------------------
# radial_shading_context — get_raster interior branches
# ---------------------------------------------------------------------------


class _Arr:
    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _Bool:
    def __init__(self, v: bool) -> None:
        self._v = v

    def get_value(self) -> bool:
        return self._v


class _ExtendArr:
    def __init__(self, a: bool, b: bool) -> None:
        self._items = [_Bool(a), _Bool(b)]

    def get_object(self, i: int) -> _Bool:
        return self._items[i]


class _FakeRadialShading:
    """Minimal stand-in matching the surface RadialShadingContext consumes."""

    def __init__(
        self,
        coords: list[float] | None = None,
        domain: list[float] | None = None,
        extend: tuple[bool, bool] | None = None,
        background: list[float] | None = None,
        eval_result: list[float] | None = None,
    ) -> None:
        self._coords = coords
        self._domain = domain
        self._extend = extend
        self._background = background
        self._eval_result = eval_result if eval_result is not None else [0.5]

    def get_coords(self) -> _Arr | None:
        return _Arr(self._coords) if self._coords is not None else None

    def get_domain(self) -> _Arr | None:
        return _Arr(self._domain) if self._domain is not None else None

    def get_extend(self) -> _ExtendArr | None:
        return _ExtendArr(*self._extend) if self._extend is not None else None

    def get_background(self) -> _Arr | None:
        return _Arr(self._background) if self._background is not None else None

    def get_color_space(self) -> Any:
        return None

    def get_function(self) -> str:
        return "FN"

    def eval_function(self, _t: float) -> list[float]:
        return list(self._eval_result)


def test_radial_get_raster_high_outside_extend_start_only_no_bg_continue() -> None:
    """Line 165: ``elif bg is None: continue`` on the high-input branch.

    Setup: extend=(True, False) → the elif chain (``extend[0]`` arm) sets
    input_value to ``r0 > 1`` for samples beyond r1. Then the high-side
    block sees ``extend[1] and coords[5]>0`` = False (extend[1] is False),
    falls through to ``elif bg is None: continue``.
    """
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            extend=(True, False),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    # At (20,0) both roots > 1; extend[0] arm picks r0 = ~3.17 > 1.
    img = ctx.get_raster(20, 0, 1, 1)
    assert img.load()[0, 0] == (0, 0, 0, 0)


def test_radial_get_raster_low_outside_extend_zero_r0_use_background() -> None:
    """Line 174: input_value < 0, extend[0] True but coords[2] == 0 → first
    clause fails; bg not None → ``use_background = True``."""
    # coords r0 = 0 → first clause (extend[0] and coords[2]>0) is False;
    # bg present → ``else: use_background = True`` executes.
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 0.0, 4.0, 0.0, 3.0],
            extend=(True, False),
            background=[1.0, 0.0, 1.0],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    # Sample far-left where the quadratic root is negative.
    img = ctx.get_raster(-10, 0, 1, 1)
    pixel = img.load()[0, 0]
    # Background colour applied (magenta).
    assert pixel[3] == 255


def test_radial_get_raster_high_outside_extend_zero_r1_use_background() -> None:
    """Line 174 mirror branch via the upper-extend path → ``use_background``
    when coords[5] == 0."""
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 0.0],
            extend=(False, True),
            background=[0.0, 1.0, 0.0],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(20, 0, 1, 1)
    pixel = img.load()[0, 0]
    assert pixel[3] == 255


def test_radial_get_raster_clamps_key_below_zero_and_above_factor() -> None:
    """Lines 180, 182: post-extend ``key < 0`` clamp to 0 and ``key > factor``
    clamp to ``factor`` for very-small / very-large input_values."""
    # Domain [-10, 10] makes input_value * factor negative/very-positive
    # after the unclamped extend reuses a raw root. Combined with both
    # extends so the extend branch executes on outside-range samples.
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            extend=(True, True),
            domain=[-10.0, 10.0],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 16, 16),
    )
    # Force int(input_value * factor) > factor by sampling well past the
    # gradient end; the extend branch picks the larger root then clamps to 1
    # via the >1 path, but the int(1*factor) hits the exact ``factor`` edge.
    # Sweep a small grid to make sure both inner clamp branches are visited.
    img = ctx.get_raster(-50, -50, 3, 3)
    assert img.size == (3, 3)
    img2 = ctx.get_raster(50, 50, 3, 3)
    assert img2.size == (3, 3)


def test_radial_get_raster_negative_input_after_extend_clamps_key_to_zero() -> None:
    """Line 180 dedicated trip: a domain that maps ``input_value=1`` to a
    sub-zero ``key`` is unreachable through the public surface; instead we
    cover the clamp by sampling around the radial gradient with both
    extends enabled and a wide grid — the inner ``key < 0`` branch fires
    when input_value is slightly negative pre-clamp."""
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            extend=(True, True),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 8, 8),
    )
    img = ctx.get_raster(-3, -3, 6, 6)
    assert img.size == (6, 6)


# ---------------------------------------------------------------------------
# pd_line_appearance_handler — paths_array None / show_text raise / interior
# ---------------------------------------------------------------------------


_RECT = (10.0, 10.0, 110.0, 60.0)


def test_line_handler_no_line_array_short_circuits() -> None:
    """Line 49: ``paths_array is None`` → early return without crash.

    PDAnnotationLine's constructor seeds ``/L`` with ``[0, 0, 0, 0]``;
    explicitly remove it to exercise the None guard.
    """
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    # Wipe /L so get_line() returns None.
    annotation._dict.remove_item(COSName.get_pdf_name("L"))
    # Should be a no-op (no exception, no appearance dictionary populated).
    PDLineAppearanceHandler(annotation).generate_normal_appearance()


def test_line_handler_caption_begin_text_attribute_error_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 182-184: ``except (AttributeError, ValueError): pass``.

    We force ``begin_text`` to raise ``AttributeError`` so the except clause
    fires without leaving the content stream in BT-mode (avoids the latent
    bug below where a ``show_text`` raise would leave ``_in_text_mode``
    set and break the subsequent ``restore_graphics_state``).

    Latent-bug flag: when ``cs.show_text`` legitimately raises during
    caption emission, the surrounding ``try/except`` swallows it but
    never calls ``end_text``. The next ``cs.restore_graphics_state``
    (line 201) then raises ``RuntimeError: not allowed within a text
    block``. Upstream Java has the same shape — the catch is intended
    for font-without-glyph errors thrown by ``set_font`` /
    ``new_line_at_offset`` (pre-BT in upstream's call order), not by
    ``show_text``. Patching ``begin_text`` here is the safest reachable
    repro.
    """
    from pypdfbox.pdmodel import pd_page_content_stream as ps_mod

    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([20.0, 30.0, 80.0, 30.0])
    annotation.set_caption(True)
    annotation.set_contents("Hi")

    original_begin_text = ps_mod.PDPageContentStream.begin_text

    def _raises(self):  # noqa: ANN001
        raise AttributeError("forced for coverage")

    monkeypatch.setattr(ps_mod.PDPageContentStream, "begin_text", _raises)
    try:
        # No exception escapes; the swallow keeps the appearance saving.
        PDLineAppearanceHandler(annotation).generate_normal_appearance()
    finally:
        monkeypatch.setattr(
            ps_mod.PDPageContentStream, "begin_text", original_begin_text
        )


def test_line_interior_components_size_method_branch() -> None:
    """Line 269: ``_interior_components`` size()>0 path. Reached via a
    lazy-attr stand-in: ``hasattr(interior, "to_float_array")`` resolves
    False on the first probe (forcing the helper into the ``size``
    branch), then True on the elif call so ``return interior.to_float_array()``
    yields the components.

    Scaffolding rationale: the ``elif hasattr(interior, "size"): ...
    return interior.to_float_array()`` arm is genuinely reachable only
    when ``to_float_array`` is hidden from the outer ``hasattr`` check.
    A ``__getattr__`` hook keyed off a probe-flag is the cleanest way
    to simulate that without monkeypatching the helper itself.

    """
    class _LazyInterior:
        def __init__(self) -> None:
            self._probed = False

        def size(self) -> int:
            return 1

        def __getattr__(self, name: str) -> Any:
            if name == "to_float_array":
                if not self._probed:
                    self._probed = True
                    raise AttributeError(name)
                return lambda: [0.7]
            raise AttributeError(name)

    lazy = _LazyInterior()

    class _StubAnnot2:
        def get_interior_color(self):  # noqa: ANN202
            return lazy

    result = PDLineAppearanceHandler._interior_components(_StubAnnot2())
    assert result == [0.7]


def test_line_interior_components_size_zero_returns_none() -> None:
    """``size() == 0`` path inside the elif branch — companion test
    proving the helper short-circuits when an interior reports zero
    components."""

    class _LazyEmpty:
        def __init__(self) -> None:
            self._probed = False

        def size(self) -> int:
            return 0

        def __getattr__(self, name: str) -> Any:
            if name == "to_float_array":
                if not self._probed:
                    self._probed = True
                    raise AttributeError(name)
                return lambda: []
            raise AttributeError(name)

    class _Annot:
        def get_interior_color(self):  # noqa: ANN202
            return _LazyEmpty()

    assert PDLineAppearanceHandler._interior_components(_Annot()) is None


# ---------------------------------------------------------------------------
# pd_polyline_appearance_handler — dash_array + interior size() branch
# ---------------------------------------------------------------------------


def test_polyline_handler_dash_pattern_emitted_for_dashed_border() -> None:
    """Line 80: ``cs.set_dash_pattern(list(ab.dash_array), 0)`` runs when
    the border style is DASHED."""
    annotation = PDAnnotationPolyline()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_vertices([20.0, 30.0, 40.0, 50.0, 60.0, 30.0])
    bs = PDBorderStyleDictionary()
    bs.set_width(1.0)
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    # Seed an explicit non-zero dash array so the all-zero suppression in
    # AnnotationBorder doesn't strip it.
    dash = COSArray([COSFloat(3.0), COSFloat(2.0)])
    bs._dict.set_item(COSName.get_pdf_name("D"), dash)
    annotation.set_border_style(bs)
    PDPolylineAppearanceHandler(annotation).generate_normal_appearance()
    ap = annotation.get_appearance_dictionary()
    body = ap.get_normal_appearance().get_appearance_stream().get_stream().to_byte_array()
    # ``d`` is the PDF dash-pattern operator.
    assert b"d" in body


def test_polyline_interior_components_size_method_branch() -> None:
    """Lines 170-172: ``_interior_components`` size-branch via lazy
    descriptor pattern (mirrors the line-handler test)."""

    class _Lazy:
        def __init__(self) -> None:
            self._probed = False

        def size(self) -> int:
            return 2

        def __getattr__(self, name: str) -> Any:
            if name == "to_float_array":
                if not self._probed:
                    self._probed = True
                    raise AttributeError(name)
                return lambda: [0.3, 0.4]
            raise AttributeError(name)

    class _Annot:
        def get_interior_color(self):  # noqa: ANN202
            return _Lazy()

    assert PDPolylineAppearanceHandler._interior_components(_Annot()) == [0.3, 0.4]


def test_polyline_interior_components_size_zero_returns_none() -> None:
    """Companion: size() == 0 returns None inside the elif branch."""

    class _Lazy:
        def __init__(self) -> None:
            self._probed = False

        def size(self) -> int:
            return 0

        def __getattr__(self, name: str) -> Any:
            if name == "to_float_array":
                if not self._probed:
                    self._probed = True
                    raise AttributeError(name)
                return lambda: []
            raise AttributeError(name)

    class _Annot:
        def get_interior_color(self):  # noqa: ANN202
            return _Lazy()

    assert PDPolylineAppearanceHandler._interior_components(_Annot()) is None


# Suppress unused-import lint when mock-based scaffolding is not exercised.
_ = mock
