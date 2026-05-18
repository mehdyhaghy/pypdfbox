"""Wave 1354 tail-sweep for the streampane subpackage.

Covers:

* ``StreamImageView.zoom_image`` rotation-only branch (line 125 in
  ``stream_image_view.py``) — exercising the ``rotation is not None``
  assignment path.
* ``StreamPane.stream_pane._ContentStreamEmitter.write_token`` operator
  dispatch (line 388 in ``stream_pane.py``).
"""

from __future__ import annotations

import tkinter as tk

import PIL.Image as PIL

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.debugger.streampane.stream_image_view import StreamImageView
from pypdfbox.debugger.streampane.stream_pane import _ContentStreamEmitter


def test_zoom_image_rotation_only_assigns_stored_rotation(tk_root: tk.Tk) -> None:
    image = PIL.new("RGB", (10, 10), color="green")
    view = StreamImageView(tk_root, image, zoom_scale=1.0, rotation_degrees=0)
    # Pass rotation but leave scale=None — hits the rotation-only branch.
    rendered = view.zoom_image(scale=None, rotation=90)
    assert rendered is not None
    # 90-degree rotation of a square keeps dimensions.
    assert rendered.size == (10, 10)
    assert view._rotation_degrees == 90  # type: ignore[attr-defined]


def test_content_stream_emitter_write_token_dispatches_operator() -> None:
    emitter = _ContentStreamEmitter()
    q = Operator.get_operator(OperatorName.SAVE)
    emitter.write_token(q)
    text = "".join(s for s, _ in emitter.segments)
    assert "q" in text
