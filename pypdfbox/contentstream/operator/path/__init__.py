from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .append_rectangle import AppendRectangle
    from .clip_even_odd import ClipEvenOdd
    from .clip_non_zero_winding import ClipNonZeroWinding
    from .close_and_stroke_path import CloseAndStrokePath
    from .close_fill_then_stroke_even_odd import CloseFillThenStrokeEvenOdd
    from .close_fill_then_stroke_non_zero_winding import CloseFillThenStrokeNonZeroWinding
    from .close_path import ClosePath
    from .curve_to import CurveTo
    from .curve_to_replicate_final_point import CurveToReplicateFinalPoint
    from .curve_to_replicate_initial_point import CurveToReplicateInitialPoint
    from .end_path_no_op import EndPathNoOp
    from .fill_path_even_odd import FillPathEvenOdd
    from .fill_path_non_zero_winding import FillPathNonZeroWinding
    from .fill_then_stroke_even_odd import FillThenStrokeEvenOdd
    from .fill_then_stroke_non_zero_winding import FillThenStrokeNonZeroWinding
    from .legacy_fill_path import LegacyFillPath
    from .line_to import LineTo
    from .move_to import MoveTo
    from .stroke_path import StrokePath

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AppendRectangle": ".append_rectangle",
        "ClipEvenOdd": ".clip_even_odd",
        "ClipNonZeroWinding": ".clip_non_zero_winding",
        "CloseAndStrokePath": ".close_and_stroke_path",
        "CloseFillThenStrokeEvenOdd": ".close_fill_then_stroke_even_odd",
        "CloseFillThenStrokeNonZeroWinding": ".close_fill_then_stroke_non_zero_winding",
        "ClosePath": ".close_path",
        "CurveTo": ".curve_to",
        "CurveToReplicateFinalPoint": ".curve_to_replicate_final_point",
        "CurveToReplicateInitialPoint": ".curve_to_replicate_initial_point",
        "EndPathNoOp": ".end_path_no_op",
        "FillPathEvenOdd": ".fill_path_even_odd",
        "FillPathNonZeroWinding": ".fill_path_non_zero_winding",
        "FillThenStrokeEvenOdd": ".fill_then_stroke_even_odd",
        "FillThenStrokeNonZeroWinding": ".fill_then_stroke_non_zero_winding",
        "LegacyFillPath": ".legacy_fill_path",
        "LineTo": ".line_to",
        "MoveTo": ".move_to",
        "StrokePath": ".stroke_path",
    },
)

__all__ = [
    "AppendRectangle",
    "ClipEvenOdd",
    "ClipNonZeroWinding",
    "CloseAndStrokePath",
    "CloseFillThenStrokeEvenOdd",
    "CloseFillThenStrokeNonZeroWinding",
    "ClosePath",
    "CurveTo",
    "CurveToReplicateFinalPoint",
    "CurveToReplicateInitialPoint",
    "EndPathNoOp",
    "FillPathEvenOdd",
    "FillPathNonZeroWinding",
    "FillThenStrokeEvenOdd",
    "FillThenStrokeNonZeroWinding",
    "LegacyFillPath",
    "LineTo",
    "MoveTo",
    "StrokePath",
]
