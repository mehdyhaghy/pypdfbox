from __future__ import annotations

# ``Concatenate`` (the ``cm`` operator) lives in ``state`` upstream
# (``org.apache.pdfbox.contentstream.operator.state.Concatenate``) but
# pypdfbox keeps the implementation under ``graphics`` for historical
# reasons (cluster #2 grouped the CTM-touching operators with the
# graphics-mutating ones). Re-export it from this package under both
# the upstream-faithful name ``Concatenate`` and pypdfbox's existing
# ``ConcatenateMatrix`` so callers can import from the same path
# upstream PDFBox developers expect.
from ..graphics.concatenate_matrix import ConcatenateMatrix
from ..graphics.concatenate_matrix import ConcatenateMatrix as Concatenate

# ``SetMatrix`` (the ``Tm`` operator) lives in ``state`` upstream
# (``org.apache.pdfbox.contentstream.operator.state.SetMatrix``) but
# pypdfbox keeps the implementation under ``text`` because the operator
# manipulates the text matrix and reads better grouped with the text
# operators. Re-export it from this package so the upstream import path
# resolves.
from ..text.set_matrix import SetMatrix
from .empty_graphics_stack_exception import EmptyGraphicsStackException
from .restore_graphics_state import RestoreGraphicsState
from .save_graphics_state import SaveGraphicsState
from .set_dash_pattern import SetDashPattern
from .set_flatness import SetFlatness
from .set_graphics_state_parameters import SetGraphicsStateParameters
from .set_line_cap_style import SetLineCapStyle
from .set_line_join_style import SetLineJoinStyle
from .set_line_miter_limit import SetLineMiterLimit
from .set_line_width import SetLineWidth
from .set_rendering_intent import SetRenderingIntent

__all__ = [
    "Concatenate",
    "ConcatenateMatrix",
    "EmptyGraphicsStackException",
    "RestoreGraphicsState",
    "SaveGraphicsState",
    "SetDashPattern",
    "SetFlatness",
    "SetGraphicsStateParameters",
    "SetLineCapStyle",
    "SetLineJoinStyle",
    "SetLineMiterLimit",
    "SetLineWidth",
    "SetMatrix",
    "SetRenderingIntent",
]
