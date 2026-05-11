from __future__ import annotations

from ..path.clip_even_odd import ClipEvenOdd
from ..path.clip_non_zero_winding import ClipNonZeroWinding
from ..path.close_path import ClosePath
from ..path.end_path_no_op import EndPathNoOp
from ..path.fill_path_even_odd import FillPathEvenOdd
from ..path.fill_path_non_zero_winding import FillPathNonZeroWinding
from ..path.stroke_path import StrokePath
from .append_rectangle_to_path import AppendRectangleToPath
from .close_fill_even_odd_and_stroke_path import CloseFillEvenOddAndStrokePath
from .close_fill_non_zero_and_stroke_path import CloseFillNonZeroAndStrokePath
from .concatenate_matrix import ConcatenateMatrix
from .fill_even_odd_and_stroke_path import FillEvenOddAndStrokePath
from .fill_non_zero_and_stroke_path import FillNonZeroAndStrokePath
from .graphics_operator_processor import GraphicsOperatorProcessor
from .invoke_named_xobject import InvokeNamedXObject
from .legacy_fill_non_zero_rule import LegacyFillNonZeroRule
from .shading_fill import ShadingFill

# Upstream-name aliases — mirror the
# ``org.apache.pdfbox.contentstream.operator.graphics`` package so that
# code ported from PDFBox can keep its original imports. These re-bind
# the existing concrete classes (which use longer descriptive names) to
# their upstream identifiers; ``DrawObject is InvokeNamedXObject``
# remains true so registry lookups, ``isinstance`` checks, and any
# previously written code continue to work unchanged.
#
# Note: ``FillNonZeroRule``, ``FillEvenOddRule``, ``ClipNonZeroRule``,
# ``ClipEvenOddRule``, ``EndPath`` are exposed here as aliases of the
# descriptive-named concrete handlers in ``path/`` for backwards
# compatibility. Fresh upstream-faithful subclasses of
# :class:`GraphicsOperatorProcessor` live under the same names in
# sibling modules (``fill_non_zero_rule.py``, ``end_path.py``, etc.)
# and can be imported directly when the engine-typed base is wanted.
DrawObject = InvokeNamedXObject
FillNonZeroRule = FillPathNonZeroWinding
FillEvenOddRule = FillPathEvenOdd
ClipNonZeroRule = ClipNonZeroWinding
ClipEvenOddRule = ClipEvenOdd
EndPath = EndPathNoOp

__all__ = [
    "AppendRectangleToPath",
    "ClipEvenOdd",
    "ClipEvenOddRule",
    "ClipNonZeroRule",
    "ClipNonZeroWinding",
    "CloseFillEvenOddAndStrokePath",
    "CloseFillNonZeroAndStrokePath",
    "ClosePath",
    "ConcatenateMatrix",
    "DrawObject",
    "EndPath",
    "EndPathNoOp",
    "FillEvenOddAndStrokePath",
    "FillEvenOddRule",
    "FillNonZeroAndStrokePath",
    "FillNonZeroRule",
    "FillPathEvenOdd",
    "FillPathNonZeroWinding",
    "GraphicsOperatorProcessor",
    "InvokeNamedXObject",
    "LegacyFillNonZeroRule",
    "ShadingFill",
    "StrokePath",
]
