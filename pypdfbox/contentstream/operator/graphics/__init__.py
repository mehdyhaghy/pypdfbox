from __future__ import annotations

from ..path.clip_even_odd import ClipEvenOdd
from ..path.clip_non_zero_winding import ClipNonZeroWinding
from ..path.close_path import ClosePath
from ..path.end_path_no_op import EndPathNoOp
from ..path.fill_path_even_odd import FillPathEvenOdd
from ..path.fill_path_non_zero_winding import FillPathNonZeroWinding
from ..path.stroke_path import StrokePath
from .concatenate_matrix import ConcatenateMatrix
from .invoke_named_xobject import InvokeNamedXObject
from .shading_fill import ShadingFill

# Upstream-name aliases — mirror the
# ``org.apache.pdfbox.contentstream.operator.graphics`` package so that
# code ported from PDFBox can keep its original imports. These re-bind
# the existing concrete classes (which use longer descriptive names) to
# their upstream identifiers; ``DrawObject is InvokeNamedXObject``
# remains true so registry lookups, ``isinstance`` checks, and any
# previously written code continue to work unchanged.
DrawObject = InvokeNamedXObject
FillNonZeroRule = FillPathNonZeroWinding
FillEvenOddRule = FillPathEvenOdd
ClipNonZeroRule = ClipNonZeroWinding
ClipEvenOddRule = ClipEvenOdd
EndPath = EndPathNoOp

__all__ = [
    "ClipEvenOdd",
    "ClipEvenOddRule",
    "ClipNonZeroRule",
    "ClipNonZeroWinding",
    "ClosePath",
    "ConcatenateMatrix",
    "DrawObject",
    "EndPath",
    "EndPathNoOp",
    "FillEvenOddRule",
    "FillNonZeroRule",
    "FillPathEvenOdd",
    "FillPathNonZeroWinding",
    "InvokeNamedXObject",
    "ShadingFill",
    "StrokePath",
]
