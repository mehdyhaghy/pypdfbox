from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSBase, COSName, COSNumber

from .operator import Operator, OperatorName
from .operator.color.set_non_stroking_cmyk import SetNonStrokingCMYK
from .operator.color.set_non_stroking_color import SetNonStrokingColor
from .operator.color.set_non_stroking_color_n import SetNonStrokingColorN
from .operator.color.set_non_stroking_color_space import SetNonStrokingColorSpace
from .operator.color.set_non_stroking_gray import SetNonStrokingGray
from .operator.color.set_non_stroking_rgb import SetNonStrokingRGB
from .operator.color.set_stroking_cmyk import SetStrokingCMYK
from .operator.color.set_stroking_color import SetStrokingColor
from .operator.color.set_stroking_color_n import SetStrokingColorN
from .operator.color.set_stroking_color_space import SetStrokingColorSpace
from .operator.color.set_stroking_gray import SetStrokingGray
from .operator.color.set_stroking_rgb import SetStrokingRGB
from .operator.graphics.concatenate_matrix import ConcatenateMatrix
from .operator.graphics.invoke_named_xobject import InvokeNamedXObject
from .operator.graphics.shading_fill import ShadingFill
from .operator.imagecontent.begin_inline_image import BeginInlineImage
from .operator.markedcontent.begin_marked_content import BeginMarkedContent
from .operator.markedcontent.begin_marked_content_with_props import (
    BeginMarkedContentWithProps,
)
from .operator.markedcontent.end_marked_content import EndMarkedContent
from .operator.path.append_rectangle import AppendRectangle
from .operator.path.clip_even_odd import ClipEvenOdd
from .operator.path.clip_non_zero_winding import ClipNonZeroWinding
from .operator.path.close_and_stroke_path import CloseAndStrokePath
from .operator.path.close_fill_then_stroke_even_odd import (
    CloseFillThenStrokeEvenOdd,
)
from .operator.path.close_fill_then_stroke_non_zero_winding import (
    CloseFillThenStrokeNonZeroWinding,
)
from .operator.path.close_path import ClosePath
from .operator.path.curve_to import CurveTo
from .operator.path.curve_to_replicate_final_point import CurveToReplicateFinalPoint
from .operator.path.curve_to_replicate_initial_point import (
    CurveToReplicateInitialPoint,
)
from .operator.path.end_path_no_op import EndPathNoOp
from .operator.path.fill_path_even_odd import FillPathEvenOdd
from .operator.path.fill_path_non_zero_winding import FillPathNonZeroWinding
from .operator.path.fill_then_stroke_even_odd import FillThenStrokeEvenOdd
from .operator.path.fill_then_stroke_non_zero_winding import (
    FillThenStrokeNonZeroWinding,
)
from .operator.path.legacy_fill_path import LegacyFillPath
from .operator.path.line_to import LineTo
from .operator.path.move_to import MoveTo
from .operator.path.stroke_path import StrokePath
from .operator.state.restore_graphics_state import RestoreGraphicsState
from .operator.state.save_graphics_state import SaveGraphicsState
from .operator.state.set_dash_pattern import SetDashPattern
from .operator.state.set_flatness import SetFlatness
from .operator.state.set_graphics_state_parameters import SetGraphicsStateParameters
from .operator.state.set_rendering_intent import SetRenderingIntent
from .operator.text.begin_text import BeginText
from .operator.text.end_text import EndText
from .operator.text.move_text import MoveText
from .operator.text.move_text_set_leading import MoveTextSetLeading
from .operator.text.next_line_op import NextLine
from .operator.text.set_char_spacing import SetCharSpacing
from .operator.text.set_font_and_size import SetFontAndSize
from .operator.text.set_horizontal_text_scaling import SetHorizontalTextScaling
from .operator.text.set_matrix import SetMatrix
from .operator.text.set_text_leading_op import SetTextLeading
from .operator.text.set_text_rendering_mode_op import SetTextRenderingMode
from .operator.text.set_text_rise_op import SetTextRise
from .operator.text.set_word_spacing_op import SetWordSpacing
from .operator.text.show_text import ShowText
from .operator.text.show_text_adjusted import ShowTextAdjusted
from .operator.text.show_text_line import ShowTextLine
from .operator.text.show_text_line_and_space import ShowTextLineAndSpace
from .pdf_stream_engine import PDFStreamEngine

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_page import PDPage


# Winding rules — mirrors java.awt.geom.Path2D.WIND_EVEN_ODD / WIND_NON_ZERO.
# Upstream PDFGraphicsStreamEngine uses these int constants in the
# ``clip(int)`` and ``fillPath(int)`` / ``fillAndStrokePath(int)`` hook
# signatures. We expose them as module-level constants so subclasses can
# refer to them by name without pulling in java.awt.
WIND_EVEN_ODD: int = 0
WIND_NON_ZERO: int = 1


class PDFGraphicsStreamEngine(PDFStreamEngine):
    """
    Abstract :class:`PDFStreamEngine` subclass for advanced graphics
    processing. Mirrors
    ``org.apache.pdfbox.contentstream.PDFGraphicsStreamEngine``.

    Subclassed by end-users hooking into graphics operations: the page
    renderer, glyph-extractor tools, content-stream rewriters, etc. The
    engine registers every standard graphics / path / clip / paint /
    state / colour / text / marked-content / image operator at
    construction so the subclass receives every relevant token routed
    through the operator dispatch loop.

    Beyond operator registration this class adds:

    - the abstract path-construction hooks (:meth:`move_to`,
      :meth:`line_to`, :meth:`curve_to`, :meth:`append_rectangle`,
      :meth:`close_path`, :meth:`get_current_point`)
    - the abstract path-painting hooks (:meth:`stroke_path`,
      :meth:`fill_path`, :meth:`fill_and_stroke_path`, :meth:`end_path`)
    - the abstract clip hook (:meth:`clip`) and shading-fill hook
      (:meth:`shading_fill`)
    - the abstract image hook (:meth:`draw_image`)
    - the :meth:`transformed_point` helper that subclasses with a CTM
      stack override to apply the current transform; the default
      passes coordinates through unchanged so a subclass can opt in to
      CTM-aware coordinates without a forced rewrite.

    Path operators dispatched by this engine pass *raw user-space*
    coordinates to the hooks; subclasses with a graphics-state stack
    are expected to call :meth:`transformed_point` themselves (or
    override the path operators) to apply the current CTM. This
    behaviour deviates from upstream which performs the transform in
    each operator handler — see ``CHANGES.md``.
    """

    def __init__(self, page: PDPage | None = None) -> None:
        super().__init__()
        self._page = page

        # Mirror upstream ``PDFGraphicsStreamEngine`` constructor: register
        # every operator processor in the order upstream registers them.
        # pypdfbox carries two parallel ``OperatorProcessor`` bases:
        #
        # - the engine-bound one in ``operator_processor.py`` (text/* ops
        #   inherit from this — they call back into engine hooks via
        #   ``get_context()``), registered via :meth:`add_operator` which
        #   also rebinds the processor's context to ``self``
        # - the lite, context-free one in
        #   ``operator/operator_processor.py`` (path/, state/, graphics/,
        #   imagecontent/, markedcontent/, color/ — purely log-and-fall-
        #   through stubs), registered directly into ``_operators``
        #
        # The path-construction / painting / clipping / image semantics
        # are routed through ``process_operator`` below — the lite stubs
        # are kept on the registry so the upstream-faithful operator-name
        # surface (``get_operators().keys()``) matches PDFBox's
        # PDFGraphicsStreamEngine instance.
        for processor in (
            CloseFillThenStrokeNonZeroWinding(),  # b
            FillThenStrokeNonZeroWinding(),       # B
            CloseFillThenStrokeEvenOdd(),         # b*
            FillThenStrokeEvenOdd(),              # B*
            BeginInlineImage(),                   # BI
            CurveTo(),                            # c
            ConcatenateMatrix(),                  # cm
            SetStrokingColorSpace(),              # CS
            SetNonStrokingColorSpace(),           # cs
            SetDashPattern(),                     # d
            InvokeNamedXObject(),                 # Do
            FillPathNonZeroWinding(),             # f
            LegacyFillPath(),                     # F
            FillPathEvenOdd(),                    # f*
            SetStrokingGray(),                    # G
            SetNonStrokingGray(),                 # g
            SetGraphicsStateParameters(),         # gs
            ClosePath(),                          # h
            SetFlatness(),                        # i
            SetStrokingCMYK(),                    # K
            SetNonStrokingCMYK(),                 # k
            LineTo(),                             # l
            MoveTo(),                             # m
            EndPathNoOp(),                        # n
            SaveGraphicsState(),                  # q
            RestoreGraphicsState(),               # Q
            AppendRectangle(),                    # re
            SetStrokingRGB(),                     # RG
            SetNonStrokingRGB(),                  # rg
            SetRenderingIntent(),                 # ri
            CloseAndStrokePath(),                 # s
            StrokePath(),                         # S
            SetStrokingColor(),                   # SC
            SetNonStrokingColor(),                # sc
            SetStrokingColorN(),                  # SCN
            SetNonStrokingColorN(),               # scn
            ShadingFill(),                        # sh
            CurveToReplicateInitialPoint(),       # v
            ClipNonZeroWinding(),                 # W
            ClipEvenOdd(),                        # W*
            CurveToReplicateFinalPoint(),         # y
            # marked-content operators (lite stubs)
            BeginMarkedContent(),                 # BMC
            BeginMarkedContentWithProps(),        # BDC
            EndMarkedContent(),                   # EMC
        ):
            # Lite stubs are scaffolding (semantics route through this
            # class' ``process_operator`` override) but we still bind the
            # engine context so ``engine.get_operator(name)._context`` is
            # consistent with upstream's ``addOperator(new X(this))``
            # invariant — every registered processor sees its engine.
            processor.set_context(self)
            self._operators[processor.get_name()] = processor  # type: ignore[assignment]

        # Device color operators need engine context so they can forward
        # PDColor values into the color-state hooks. They overwrite the
        # context-free instances registered above.
        for color_processor in (
            SetStrokingGray(),                     # G
            SetNonStrokingGray(),                  # g
            SetStrokingRGB(),                      # RG
            SetNonStrokingRGB(),                   # rg
            SetStrokingCMYK(),                     # K
            SetNonStrokingCMYK(),                  # k
        ):
            self.add_operator(color_processor)  # type: ignore[arg-type]

        # Engine-bound text-operator handlers (call back into engine hooks
        # via ``get_context()``). These need ``add_operator`` so the
        # ``set_context`` rebind happens.
        for engine_bound in (
            BeginText(),                          # BT
            EndText(),                            # ET
            NextLine(),                           # T*
            MoveText(),                           # Td
            MoveTextSetLeading(),                 # TD
            SetFontAndSize(),                     # Tf
            SetMatrix(),                          # Tm
            SetCharSpacing(),                     # Tc
            SetTextLeading(),                     # TL
            SetTextRenderingMode(),               # Tr
            SetTextRise(),                        # Ts
            SetWordSpacing(),                     # Tw
            SetHorizontalTextScaling(),           # Tz
            ShowText(),                           # Tj
            ShowTextAdjusted(),                   # TJ
            ShowTextLine(),                       # '
            ShowTextLineAndSpace(),               # "
        ):
            self.add_operator(engine_bound)

    # ---------- accessors ----------

    def get_page(self) -> PDPage | None:
        """Return the page the content stream belongs to (or ``None``
        for tiling patterns and other pageless streams). Mirrors
        upstream ``PDFGraphicsStreamEngine.getPage``."""
        return self._page

    # ---------- coordinate transform helper ----------

    def transformed_point(self, x: float, y: float) -> tuple[float, float]:
        """Map a user-space point through the current CTM.

        Default implementation: identity (returns ``(x, y)`` unchanged).
        Subclasses with a graphics-state stack — chiefly the rendering
        subclass — override this to apply the current CTM. Mirrors
        upstream ``PDFStreamEngine.transformedPoint``; lifted to this
        class so subclasses can rely on a single transform helper
        regardless of whether a CTM stack is present.
        """
        return (float(x), float(y))

    # ---------- dispatch override ----------
    #
    # The lite operator stubs registered above are no-ops (they just log).
    # We override ``process_operator`` to *also* invoke the abstract
    # graphics hooks for the operators that drive path construction /
    # painting / clipping / image drawing. This keeps the upstream-faithful
    # operator registry while routing the semantic events through the
    # abstract methods this class exposes.

    def process_operator(
        self,
        operator: Operator | str,
        operands: list[COSBase] | None,
    ) -> None:
        if operands is None:
            operands = []
        if isinstance(operator, str):
            operator = Operator.get_operator(operator)
        name = operator.get_name()

        # Path construction
        if name == OperatorName.MOVE_TO:
            x = self._coerce_float(operands, 0)
            y = self._coerce_float(operands, 1)
            if x is None or y is None:
                return
            tx, ty = self.transformed_point(x, y)
            self.move_to(tx, ty)
            return
        if name == OperatorName.LINE_TO:
            x = self._coerce_float(operands, 0)
            y = self._coerce_float(operands, 1)
            if x is None or y is None:
                return
            tx, ty = self.transformed_point(x, y)
            self.line_to(tx, ty)
            return
        if name == OperatorName.CURVE_TO:
            coords = self._coerce_floats(operands, 6)
            if coords is None:
                return
            x1, y1, x2, y2, x3, y3 = coords
            p1 = self.transformed_point(x1, y1)
            p2 = self.transformed_point(x2, y2)
            p3 = self.transformed_point(x3, y3)
            self.curve_to(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
            return
        if name == OperatorName.CURVE_TO_REPLICATE_INITIAL_POINT:
            # v: first control point = current point
            coords = self._coerce_floats(operands, 4)
            if coords is None:
                return
            x2, y2, x3, y3 = coords
            current = self.get_current_point()
            if current is None:
                return
            p2 = self.transformed_point(x2, y2)
            p3 = self.transformed_point(x3, y3)
            self.curve_to(current[0], current[1], p2[0], p2[1], p3[0], p3[1])
            return
        if name == OperatorName.CURVE_TO_REPLICATE_FINAL_POINT:
            # y: second control point = end point
            coords = self._coerce_floats(operands, 4)
            if coords is None:
                return
            x1, y1, x3, y3 = coords
            p1 = self.transformed_point(x1, y1)
            p3 = self.transformed_point(x3, y3)
            self.curve_to(p1[0], p1[1], p3[0], p3[1], p3[0], p3[1])
            return
        if name == OperatorName.APPEND_RECT:
            coords = self._coerce_floats(operands, 4)
            if coords is None:
                return
            x, y, w, h = coords
            p0 = self.transformed_point(x, y)
            p1 = self.transformed_point(x + w, y)
            p2 = self.transformed_point(x + w, y + h)
            p3 = self.transformed_point(x, y + h)
            self.append_rectangle(p0, p1, p2, p3)
            return
        if name == OperatorName.CLOSE_PATH:
            self.close_path()
            return

        # Path painting
        if name == OperatorName.STROKE_PATH:
            self.stroke_path()
            return
        if name == OperatorName.CLOSE_AND_STROKE:
            self.close_path()
            self.stroke_path()
            return
        if name == OperatorName.FILL_NON_ZERO:
            self.fill_path(WIND_NON_ZERO)
            return
        if name == OperatorName.LEGACY_FILL_NON_ZERO:
            self.fill_path(WIND_NON_ZERO)
            return
        if name == OperatorName.FILL_EVEN_ODD:
            self.fill_path(WIND_EVEN_ODD)
            return
        if name == OperatorName.FILL_NON_ZERO_AND_STROKE:
            self.fill_and_stroke_path(WIND_NON_ZERO)
            return
        if name == OperatorName.FILL_EVEN_ODD_AND_STROKE:
            self.fill_and_stroke_path(WIND_EVEN_ODD)
            return
        if name == OperatorName.CLOSE_FILL_NON_ZERO_AND_STROKE:
            self.close_path()
            self.fill_and_stroke_path(WIND_NON_ZERO)
            return
        if name == OperatorName.CLOSE_FILL_EVEN_ODD_AND_STROKE:
            self.close_path()
            self.fill_and_stroke_path(WIND_EVEN_ODD)
            return
        if name == OperatorName.ENDPATH:
            self.end_path()
            return

        # Clipping
        if name == OperatorName.CLIP_NON_ZERO:
            self.clip(WIND_NON_ZERO)
            return
        if name == OperatorName.CLIP_EVEN_ODD:
            self.clip(WIND_EVEN_ODD)
            return

        # Graphics-state save / restore — drive the engine hooks the
        # parent already exposes (save_graphics_state / restore_graphics_state).
        # The lite ``q`` / ``Q`` stubs registered above only log;
        # forwarding here gives subclasses a single hook to override.
        if name == OperatorName.SAVE:
            self.save_graphics_state()
            return
        if name == OperatorName.RESTORE:
            self.restore_graphics_state()
            return

        # Shading fill
        if name == OperatorName.SHADING_FILL:
            shading_name: COSName | None = None
            if operands and isinstance(operands[0], COSName):
                shading_name = operands[0]
            if shading_name is not None:
                self.shading_fill(shading_name)
            return

        # Anything else: defer to the standard registered-processor path
        # (q / Q / cm / colour / text / Do / BI / marked content /
        # set-state operators) — those drive the existing engine hooks
        # (save_graphics_state / restore_graphics_state / begin_text /
        # end_text / show_text_string / etc.) without further wiring.
        super().process_operator(operator, operands)

    # ---------- abstract hooks ----------

    def append_rectangle(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
    ) -> None:
        """Append a rectangle to the current path. ``p0``..``p3`` are the
        four corners (already transformed if the subclass overrides
        :meth:`transformed_point`). Mirrors upstream
        ``appendRectangle(Point2D p0, Point2D p1, Point2D p2, Point2D p3)``.
        """
        raise NotImplementedError

    def draw_image(self, pd_image: Any) -> None:
        """Draw the image. Mirrors upstream
        ``drawImage(PDImage pdImage)``. ``pd_image`` is a
        :class:`PDImageXObject`-shaped object (no ``PDImage`` interface
        is defined in pypdfbox at this stage; subclasses receive the
        concrete image type used by their content stream)."""
        raise NotImplementedError

    def show_inline_image(self, inline_image: Any) -> None:
        """Forward inline-image dispatch to :meth:`draw_image`. Mirrors
        upstream ``PDFGraphicsStreamEngine.showInlineImage`` which
        delegates ``PDInlineImage`` arrivals through the same paint path
        as XObject images so subclasses don't need to model the two
        forms separately."""
        self.draw_image(inline_image)

    def clip(self, winding_rule: int) -> None:
        """Modify the current clipping path by intersecting it with the
        current path. The clipping path is not updated until the
        succeeding painting (or ``n``) operator. ``winding_rule`` is
        :data:`WIND_NON_ZERO` or :data:`WIND_EVEN_ODD`. Mirrors upstream
        ``clip(int)``."""
        raise NotImplementedError

    def move_to(self, x: float, y: float) -> None:
        """Begin a new subpath at ``(x, y)``. Mirrors upstream
        ``moveTo(float x, float y)``."""
        raise NotImplementedError

    def line_to(self, x: float, y: float) -> None:
        """Append a straight-line segment from the current point to
        ``(x, y)``. Mirrors upstream ``lineTo(float x, float y)``."""
        raise NotImplementedError

    def curve_to(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> None:
        """Append a Bézier curve from the current point to ``(x3, y3)``
        with control points ``(x1, y1)`` and ``(x2, y2)``. Mirrors
        upstream ``curveTo(float, float, float, float, float, float)``."""
        raise NotImplementedError

    def get_current_point(self) -> tuple[float, float] | None:
        """Return the current point of the current path, or ``None``
        when no subpath is open. Mirrors upstream ``getCurrentPoint``
        (which returns ``Point2D`` / ``null``)."""
        raise NotImplementedError

    def close_path(self) -> None:
        """Close the current subpath. Mirrors upstream ``closePath``."""
        raise NotImplementedError

    def end_path(self) -> None:
        """End the current path without filling or stroking it. The
        clipping path is updated here. Mirrors upstream ``endPath``."""
        raise NotImplementedError

    def stroke_path(self) -> None:
        """Stroke the current path. Mirrors upstream ``strokePath``."""
        raise NotImplementedError

    def fill_path(self, winding_rule: int) -> None:
        """Fill the current path using the given winding rule
        (:data:`WIND_NON_ZERO` or :data:`WIND_EVEN_ODD`). Mirrors
        upstream ``fillPath(int)``."""
        raise NotImplementedError

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        """Fill and then stroke the current path. Mirrors upstream
        ``fillAndStrokePath(int)``."""
        raise NotImplementedError

    def shading_fill(self, shading_name: COSName) -> None:
        """Fill the current path with a shading dictionary. Mirrors
        upstream ``shadingFill(COSName)``."""
        raise NotImplementedError

    # ---------- helpers ----------

    @staticmethod
    def _coerce_float(operands: list[COSBase], index: int) -> float | None:
        if index >= len(operands):
            return None
        v = operands[index]
        if isinstance(v, COSNumber):
            return v.float_value()
        return None

    @staticmethod
    def _coerce_floats(
        operands: list[COSBase], count: int
    ) -> tuple[float, ...] | None:
        if len(operands) < count:
            return None
        out: list[float] = []
        for i in range(count):
            v = operands[i]
            if not isinstance(v, COSNumber):
                return None
            out.append(v.float_value())
        return tuple(out)


__all__ = [
    "PDFGraphicsStreamEngine",
    "WIND_EVEN_ODD",
    "WIND_NON_ZERO",
]
