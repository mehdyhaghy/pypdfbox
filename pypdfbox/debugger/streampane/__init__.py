"""Tkinter port of ``org.apache.pdfbox.debugger.streampane``.

Hosts the StreamPane subsystem which renders a ``COSStream`` either as
syntax-highlighted content-stream text or as a decoded inline image.
The Swing-only sibling subpackage ``tooltip`` is owned by a separate
wave-1293 agent.
"""

from __future__ import annotations

from pypdfbox.debugger.streampane.operator_marker import OperatorMarker
from pypdfbox.debugger.streampane.stream import Stream
from pypdfbox.debugger.streampane.stream_image_view import StreamImageView
from pypdfbox.debugger.streampane.stream_pane import StreamPane
from pypdfbox.debugger.streampane.stream_pane_view import StreamPaneView
from pypdfbox.debugger.streampane.stream_text_view import StreamTextView

__all__ = [
    "OperatorMarker",
    "Stream",
    "StreamImageView",
    "StreamPane",
    "StreamPaneView",
    "StreamTextView",
]
