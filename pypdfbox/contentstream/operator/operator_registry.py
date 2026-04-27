from __future__ import annotations

from typing import ClassVar

from pypdfbox.cos import COSBase

from . import Operator
from .color.set_non_stroking_cmyk import SetNonStrokingCMYK
from .color.set_non_stroking_color import SetNonStrokingColor
from .color.set_non_stroking_color_n import SetNonStrokingColorN
from .color.set_non_stroking_color_space import SetNonStrokingColorSpace
from .color.set_non_stroking_gray import SetNonStrokingGray
from .color.set_non_stroking_rgb import SetNonStrokingRGB
from .color.set_stroking_cmyk import SetStrokingCMYK
from .color.set_stroking_color import SetStrokingColor
from .color.set_stroking_color_n import SetStrokingColorN
from .color.set_stroking_color_space import SetStrokingColorSpace
from .color.set_stroking_gray import SetStrokingGray
from .color.set_stroking_rgb import SetStrokingRGB
from .graphics.concatenate_matrix import ConcatenateMatrix
from .graphics.invoke_named_xobject import InvokeNamedXObject
from .imagecontent.begin_inline_image import BeginInlineImage
from .imagecontent.begin_inline_image_data import BeginInlineImageData
from .imagecontent.end_inline_image import EndInlineImage
from .markedcontent.begin_marked_content import BeginMarkedContent
from .markedcontent.begin_marked_content_with_props import (
    BeginMarkedContentWithProps,
)
from .markedcontent.define_marked_content_point import (
    DefineMarkedContentPoint,
)
from .markedcontent.define_marked_content_point_with_props import (
    DefineMarkedContentPointWithProps,
)
from .markedcontent.end_marked_content import EndMarkedContent
from .operator_processor import OperatorProcessor
from .path.append_rectangle import AppendRectangle
from .path.clip_even_odd import ClipEvenOdd
from .path.clip_non_zero_winding import ClipNonZeroWinding
from .path.close_and_stroke_path import CloseAndStrokePath
from .path.close_fill_then_stroke_even_odd import CloseFillThenStrokeEvenOdd
from .path.close_fill_then_stroke_non_zero_winding import (
    CloseFillThenStrokeNonZeroWinding,
)
from .path.close_path import ClosePath
from .path.curve_to import CurveTo
from .path.curve_to_replicate_final_point import CurveToReplicateFinalPoint
from .path.curve_to_replicate_initial_point import (
    CurveToReplicateInitialPoint,
)
from .path.end_path_no_op import EndPathNoOp
from .path.fill_path_even_odd import FillPathEvenOdd
from .path.fill_path_non_zero_winding import FillPathNonZeroWinding
from .path.fill_then_stroke_even_odd import FillThenStrokeEvenOdd
from .path.fill_then_stroke_non_zero_winding import (
    FillThenStrokeNonZeroWinding,
)
from .path.legacy_fill_path import LegacyFillPath
from .path.line_to import LineTo
from .path.move_to import MoveTo
from .path.stroke_path import StrokePath
from .state.restore_graphics_state import RestoreGraphicsState
from .state.save_graphics_state import SaveGraphicsState
from .state.set_dash_pattern import SetDashPattern
from .state.set_flatness import SetFlatness
from .state.set_graphics_state_parameters import SetGraphicsStateParameters
from .state.set_line_cap_style import SetLineCapStyle
from .state.set_line_join_style import SetLineJoinStyle
from .state.set_line_miter_limit import SetLineMiterLimit
from .state.set_line_width import SetLineWidth
from .state.set_rendering_intent import SetRenderingIntent
from .text.move_text_position import MoveTextPosition
from .text.move_text_set_leading_handler import MoveTextSetLeading
from .text.next_line import NextLine
from .text.set_character_spacing import SetCharacterSpacing
from .text.set_font_and_size_handler import SetFontAndSize
from .text.set_horizontal_scaling import SetHorizontalScaling
from .text.set_text_leading import SetTextLeading
from .text.set_text_matrix import SetTextMatrix
from .text.set_text_rendering_mode import SetTextRenderingMode
from .text.set_text_rise import SetTextRise
from .text.set_word_spacing import SetWordSpacing
from .text.show_text_array import ShowTextArray
from .text.show_text_handler import ShowText
from .text.show_text_with_position import ShowTextWithPosition
from .text.show_text_with_word_and_char_spacing import (
    ShowTextWithWordAndCharSpacing,
)


class OperatorRegistry:
    """
    Operator-name to :class:`OperatorProcessor` dispatcher.

    Sibling of the engine-coupled registration on
    :class:`PDFStreamEngine`: where the engine binds each processor to
    itself via ``add_operator``, this registry stores plain processor
    classes (instantiated lazily on lookup) so it can be used for
    operator routing without an engine context.

    Mirrors the conceptual shape of upstream PDFBox's per-engine
    operator map but factored out as a standalone object so tooling
    code (parser-only consumers, validators, future content-stream
    rewriters) can route operators to handlers without spinning up a
    full :class:`PDFStreamEngine`.

    Defaults are populated from :attr:`_DEFAULT_HANDLERS` at
    construction; callers override or extend with :meth:`register`.
    """

    _DEFAULT_HANDLERS: ClassVar[dict[str, type[OperatorProcessor]]] = {
        # text-showing operators
        ShowText.OPERATOR_NAME: ShowText,
        ShowTextArray.OPERATOR_NAME: ShowTextArray,
        ShowTextWithPosition.OPERATOR_NAME: ShowTextWithPosition,
        ShowTextWithWordAndCharSpacing.OPERATOR_NAME: (
            ShowTextWithWordAndCharSpacing
        ),
        # text-state / positioning operators
        SetFontAndSize.OPERATOR_NAME: SetFontAndSize,
        MoveTextPosition.OPERATOR_NAME: MoveTextPosition,
        MoveTextSetLeading.OPERATOR_NAME: MoveTextSetLeading,
        SetTextMatrix.OPERATOR_NAME: SetTextMatrix,
        SetTextRenderingMode.OPERATOR_NAME: SetTextRenderingMode,
        SetTextRise.OPERATOR_NAME: SetTextRise,
        SetCharacterSpacing.OPERATOR_NAME: SetCharacterSpacing,
        SetWordSpacing.OPERATOR_NAME: SetWordSpacing,
        SetHorizontalScaling.OPERATOR_NAME: SetHorizontalScaling,
        SetTextLeading.OPERATOR_NAME: SetTextLeading,
        NextLine.OPERATOR_NAME: NextLine,
        # graphics-state operators
        SaveGraphicsState.OPERATOR_NAME: SaveGraphicsState,
        RestoreGraphicsState.OPERATOR_NAME: RestoreGraphicsState,
        ConcatenateMatrix.OPERATOR_NAME: ConcatenateMatrix,
        SetDashPattern.OPERATOR_NAME: SetDashPattern,
        SetFlatness.OPERATOR_NAME: SetFlatness,
        SetRenderingIntent.OPERATOR_NAME: SetRenderingIntent,
        SetGraphicsStateParameters.OPERATOR_NAME: SetGraphicsStateParameters,
        SetLineWidth.OPERATOR_NAME: SetLineWidth,
        SetLineCapStyle.OPERATOR_NAME: SetLineCapStyle,
        SetLineJoinStyle.OPERATOR_NAME: SetLineJoinStyle,
        SetLineMiterLimit.OPERATOR_NAME: SetLineMiterLimit,
        # XObject invocation
        InvokeNamedXObject.OPERATOR_NAME: InvokeNamedXObject,
        # inline-image operators
        BeginInlineImage.OPERATOR_NAME: BeginInlineImage,
        BeginInlineImageData.OPERATOR_NAME: BeginInlineImageData,
        EndInlineImage.OPERATOR_NAME: EndInlineImage,
        # path-construction operators
        MoveTo.OPERATOR_NAME: MoveTo,
        LineTo.OPERATOR_NAME: LineTo,
        CurveTo.OPERATOR_NAME: CurveTo,
        CurveToReplicateInitialPoint.OPERATOR_NAME: (
            CurveToReplicateInitialPoint
        ),
        CurveToReplicateFinalPoint.OPERATOR_NAME: CurveToReplicateFinalPoint,
        ClosePath.OPERATOR_NAME: ClosePath,
        AppendRectangle.OPERATOR_NAME: AppendRectangle,
        # path-painting operators
        StrokePath.OPERATOR_NAME: StrokePath,
        CloseAndStrokePath.OPERATOR_NAME: CloseAndStrokePath,
        FillPathNonZeroWinding.OPERATOR_NAME: FillPathNonZeroWinding,
        FillPathEvenOdd.OPERATOR_NAME: FillPathEvenOdd,
        LegacyFillPath.OPERATOR_NAME: LegacyFillPath,
        FillThenStrokeNonZeroWinding.OPERATOR_NAME: (
            FillThenStrokeNonZeroWinding
        ),
        CloseFillThenStrokeNonZeroWinding.OPERATOR_NAME: (
            CloseFillThenStrokeNonZeroWinding
        ),
        FillThenStrokeEvenOdd.OPERATOR_NAME: FillThenStrokeEvenOdd,
        CloseFillThenStrokeEvenOdd.OPERATOR_NAME: CloseFillThenStrokeEvenOdd,
        EndPathNoOp.OPERATOR_NAME: EndPathNoOp,
        # clipping operators
        ClipNonZeroWinding.OPERATOR_NAME: ClipNonZeroWinding,
        ClipEvenOdd.OPERATOR_NAME: ClipEvenOdd,
        # colour operators
        SetStrokingColorSpace.OPERATOR_NAME: SetStrokingColorSpace,
        SetNonStrokingColorSpace.OPERATOR_NAME: SetNonStrokingColorSpace,
        SetStrokingColor.OPERATOR_NAME: SetStrokingColor,
        SetStrokingColorN.OPERATOR_NAME: SetStrokingColorN,
        SetNonStrokingColor.OPERATOR_NAME: SetNonStrokingColor,
        SetNonStrokingColorN.OPERATOR_NAME: SetNonStrokingColorN,
        SetStrokingGray.OPERATOR_NAME: SetStrokingGray,
        SetNonStrokingGray.OPERATOR_NAME: SetNonStrokingGray,
        SetStrokingRGB.OPERATOR_NAME: SetStrokingRGB,
        SetNonStrokingRGB.OPERATOR_NAME: SetNonStrokingRGB,
        SetStrokingCMYK.OPERATOR_NAME: SetStrokingCMYK,
        SetNonStrokingCMYK.OPERATOR_NAME: SetNonStrokingCMYK,
        # marked-content operators
        BeginMarkedContent.OPERATOR_NAME: BeginMarkedContent,
        BeginMarkedContentWithProps.OPERATOR_NAME: (
            BeginMarkedContentWithProps
        ),
        EndMarkedContent.OPERATOR_NAME: EndMarkedContent,
        DefineMarkedContentPoint.OPERATOR_NAME: DefineMarkedContentPoint,
        DefineMarkedContentPointWithProps.OPERATOR_NAME: (
            DefineMarkedContentPointWithProps
        ),
    }

    def __init__(self) -> None:
        self._handlers: dict[str, type[OperatorProcessor]] = dict(
            self._DEFAULT_HANDLERS
        )

    # ---------- registration ----------

    def register(
        self, name: str, processor_class: type[OperatorProcessor]
    ) -> None:
        """Register (or override) the handler class for ``name``."""
        self._handlers[name] = processor_class

    # ---------- lookup ----------

    def lookup(self, name: str) -> OperatorProcessor | None:
        """Return a fresh handler instance for ``name``, or ``None`` if
        no handler is registered. A new instance per lookup keeps each
        dispatch independent — handlers may carry per-invocation state
        in subclasses without leaking across operators."""
        cls = self._handlers.get(name)
        if cls is None:
            return None
        return cls()

    # ---------- dispatch ----------

    def process(
        self, operator: Operator, operands: list[COSBase]
    ) -> None:
        """Look up the handler for ``operator`` and call its
        :meth:`OperatorProcessor.process`. Unknown operators are
        silently skipped — matching the lenient default upstream
        ``PDFStreamEngine.unsupportedOperator`` shape."""
        handler = self.lookup(operator.get_name())
        if handler is None:
            return
        handler.process(operator, operands)


__all__ = ["OperatorRegistry"]
