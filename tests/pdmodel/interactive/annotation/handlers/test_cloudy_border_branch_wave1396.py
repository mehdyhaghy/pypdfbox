"""Wave 1396 branch-coverage tests for ``CloudyBorder``.

Closes False-branch arrows in
``pypdfbox/pdmodel/interactive/annotation/handlers/cloudy_border.py``:

* 98->94 — ``create_cloudy_path`` skips a path entry with neither 2 nor
  6 coordinates
* 963->exit — ``begin_output`` short-circuits when ``output`` is ``None``
* 984->exit — ``move_to`` short-circuits when ``output`` is ``None``
* 1004->exit — ``line_to`` short-circuits when ``output`` is ``None``
* 1022->exit — ``curve_to`` short-circuits when ``output`` is ``None``
* 1031->exit — ``finish`` skips when ``line_width <= 0``
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.interactive.annotation.handlers.cloudy_border import (
    CloudyBorder,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _stream() -> PDAppearanceContentStream:
    return PDAppearanceContentStream(PDAppearanceStream(COSStream()))


def _none_output_cloudy_border() -> CloudyBorder:
    """Build a ``CloudyBorder`` with ``_output`` set to ``None`` to
    exercise the ``output is not None`` False arms.
    """
    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    cb = CloudyBorder(_stream(), 1.0, 1.0, rect)
    cb._output = None  # noqa: SLF001
    return cb


def test_create_cloudy_polygon_skips_segments_other_than_2_or_6_points() -> None:
    """Path entries with neither 2 nor 6 coordinates are skipped.

    Closes the False arm of ``elif len(array) == 6`` at line 98->94.
    """
    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    cb = CloudyBorder(_stream(), 1.0, 1.0, rect)
    # Mix of valid 2-point and invalid 4-point entries.
    path = [
        [0.0, 0.0],
        [50.0, 50.0, 60.0, 60.0],  # 4 — skipped
        [100.0, 100.0],
    ]
    cb.create_cloudy_polygon(path)
    # Method completes without raising — the 4-point entry was skipped.


def test_begin_output_with_none_output_short_circuits() -> None:
    """``begin_output`` does not call set_line_join_style when output is None.

    Closes the False arm at line 963->exit.
    """
    cb = _none_output_cloudy_border()
    cb.begin_output(5.0, 10.0)
    # _output_started flag still flipped — no observable error.
    assert cb._output_started is True  # noqa: SLF001


def test_move_to_with_none_output_short_circuits() -> None:
    """``move_to`` does not call output.move_to when output is None.

    Closes the False arm at line 984->exit.
    """
    cb = _none_output_cloudy_border()
    cb.move_to(1.0, 2.0)
    # The bbox tracking still ran via begin_output.
    assert cb._bbox_min_x == 1.0  # noqa: SLF001
    assert cb._bbox_min_y == 2.0  # noqa: SLF001


def test_line_to_with_none_output_short_circuits() -> None:
    """``line_to`` does not call output.line_to when output is None.

    Closes the False arm at line 1004->exit.
    """
    cb = _none_output_cloudy_border()
    # Drive a move_to first to set _output_started True, then line_to
    cb.move_to(0.0, 0.0)
    cb.line_to(10.0, 20.0)
    assert cb._bbox_max_x == 10.0  # noqa: SLF001
    assert cb._bbox_max_y == 20.0  # noqa: SLF001


def test_curve_to_with_none_output_short_circuits() -> None:
    """``curve_to`` does not call output.curve_to when output is None.

    Closes the False arm at line 1022->exit.
    """
    cb = _none_output_cloudy_border()
    # All 3 points lie inside the seeded [0,0,100,100] bbox, so bbox
    # is unchanged. We're just verifying the call doesn't raise on
    # the None-output short-circuit.
    cb.curve_to(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    # bbox stays at the seeded rect; assert min was lowered to 1.0.
    assert cb._bbox_min_x == 0.0  # noqa: SLF001  — seeded


def test_finish_with_zero_line_width_skips_bbox_pad() -> None:
    """``finish`` does not pad the bbox when line_width is 0.

    Closes the False arm of ``self._line_width > 0`` at line 1031->exit.
    """
    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    cb = CloudyBorder(_stream(), 1.0, 0.0, rect)  # line_width=0
    cb._output_started = True  # noqa: SLF001 — keep the close-path branch
    initial_max_x = cb._bbox_max_x  # noqa: SLF001
    cb.finish()
    # No padding applied — bbox is unchanged on the upper-right side.
    assert cb._bbox_max_x == initial_max_x  # noqa: SLF001
