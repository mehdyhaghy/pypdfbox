from __future__ import annotations

# ``ConcatenateMatrix`` is the original pypdfbox handler that performs
# the actual CTM mutation (the upstream-named ``Concatenate`` parity
# class delegates to it). The dedicated ``concatenate.py`` module hosts
# the upstream-named parity surface; we re-export both here so callers
# can import either name from this package.
from ..graphics.concatenate_matrix import ConcatenateMatrix

# ``SetMatrix`` (the ``Tm`` operator) lives in ``state`` upstream
# (``org.apache.pdfbox.contentstream.operator.state.SetMatrix``) but
# pypdfbox keeps the implementation under ``text`` because the operator
# manipulates the text matrix and reads better grouped with the text
# operators. Re-export it from this package so the upstream import path
# resolves.
from ..text.set_matrix import SetMatrix
from .concatenate import Concatenate
from .empty_graphics_stack_exception import EmptyGraphicsStackException
from .restore import Restore
from .restore_graphics_state import RestoreGraphicsState
from .save import Save
from .save_graphics_state import SaveGraphicsState
from .set_dash_pattern import SetDashPattern
from .set_flatness import SetFlatness
from .set_graphics_state_parameters import SetGraphicsStateParameters
from .set_line_cap_style import SetLineCapStyle
from .set_line_dash_pattern import SetLineDashPattern
from .set_line_join_style import SetLineJoinStyle
from .set_line_miter_limit import SetLineMiterLimit
from .set_line_width import SetLineWidth
from .set_rendering_intent import SetRenderingIntent

__all__ = [
    "Concatenate",
    "ConcatenateMatrix",
    "EmptyGraphicsStackException",
    "Restore",
    "RestoreGraphicsState",
    "Save",
    "SaveGraphicsState",
    "SetDashPattern",
    "SetFlatness",
    "SetGraphicsStateParameters",
    "SetLineCapStyle",
    "SetLineDashPattern",
    "SetLineJoinStyle",
    "SetLineMiterLimit",
    "SetLineWidth",
    "SetMatrix",
    "SetRenderingIntent",
]
