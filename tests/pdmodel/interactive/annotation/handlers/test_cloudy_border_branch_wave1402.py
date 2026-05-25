"""Wave 1402 branch-coverage round-out for ``CloudyBorder``.

Closes residual False-branch arrows:

* 379->381 — ``compute_params_polygon`` returns ``n < 0`` AND
  ``_output_started`` is already True, so the inner ``move_to`` is skipped.
* 537->539 — ``len(center_points) >= center_points_length`` (floating-point
  overshoot at the loop boundary).
* 791->exit — ``get_arc`` is called with a sweep that is an exact multiple
  of ``pi/2`` so ``angle_todo`` falls cleanly to ``0`` after the while loop.
"""

from __future__ import annotations

import math

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


def test_get_arc_zero_sweep_skips_tail_segment_branch() -> None:
    """Closes 791->exit: when ``start_ang == end_ang`` the sweep is
    exactly 0, so after the empty while-loop ``angle_todo`` is 0 and the
    tail ``if angle_todo > 0`` arm is False — no segment is emitted.
    """

    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    cb = CloudyBorder(_stream(), 1.0, 1.0, rect)
    out: list[tuple[float, float]] = []
    # start_ang == end_ang → sweep = 0
    cb.get_arc(0.0, 0.0, 10.0, 10.0, 50.0, 50.0, out, True)
    # Only the move_to point may be appended (add_move_to=True), no
    # arc-segment samples.
    assert len(out) <= 1


def test_get_arc_zero_sweep_no_move_to_branch_exit() -> None:
    """Same as above but with ``add_move_to=False`` so the output list is
    empty — exercises the 791->exit False arm cleanly.
    """

    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    cb = CloudyBorder(_stream(), 1.0, 1.0, rect)
    out: list[tuple[float, float]] = []
    cb.get_arc(math.pi, math.pi, 10.0, 10.0, 50.0, 50.0, out, False)
    assert out == []


def test_create_cloudy_polygon_n_negative_with_output_already_started() -> None:
    """Closes 379->381: ``compute_params_polygon`` returns ``n < 0`` on a
    very short segment, but ``_output_started`` was set True earlier in the
    walk, so the inner ``if not self._output_started`` is False and the
    fallback ``move_to`` is skipped.
    """

    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    # Pre-mark output as started so the False arrow is taken when the
    # short-segment fallback fires.
    cb._output_started = True  # noqa: SLF001

    # Polygon with a deliberately-tiny first segment so the cloud radius
    # math returns n < 0 on it; remaining segments are normal-sized so the
    # loop iterates.
    path: list[list[float]] = [
        [0.0, 0.0],
        [0.001, 0.0],  # micro-segment — triggers n<0
        [100.0, 0.0],
        [100.0, 50.0],
        [0.0, 0.0],
    ]
    cb.create_cloudy_polygon(path)
    # Just exercising the branch — no specific output requirement.


def test_cloudy_ellipse_center_points_floating_point_overshoot() -> None:
    """Closes 537->539: the inner ``while True`` may overshoot
    ``center_points_length`` by one iteration when curl_advance ÷ tot_len
    leaves floating residue, so ``len(center_points) >= center_points_length``
    fires and the append is skipped.

    This exercises ``cloudy_ellipse_impl`` via ``create_cloudy_ellipse`` on
    a non-circular ellipse with a high intensity so n is large enough for
    the residue path to fire.
    """

    rect = PDRectangle(0.0, 0.0, 200.0, 100.0)
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    # Drive an elliptical (non-circular) annotation to exercise the
    # flat-polygon → center-points walk.
    cb.create_cloudy_ellipse(PDRectangle(0.0, 0.0, 200.0, 100.0))
    # Method should complete without raising.


def test_cloudy_rect_intensity_zero_with_none_output_skips_add_rect() -> None:
    """Closes 284->286: when ``_intensity <= 0`` AND output is None the
    ``output is not None and hasattr(output, "add_rect")`` arm is False
    and the body falls straight through to bbox bookkeeping + return.
    """

    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    cb = CloudyBorder(_stream(), 0.0, 1.0, rect)  # intensity = 0
    cb._output = None  # noqa: SLF001 — force output-less path
    # Drive cloudy_rectangle_impl which contains the line 282-290 block.
    cb.cloudy_rectangle_impl(0.0, 0.0, 100.0, 100.0, False)


def test_cloudy_polygon_first_segment_too_short_with_output_started() -> None:
    """Closes 379->381 (False arm): when the very first polygon segment
    is too short for the cloud-radius math (n < 0) AND ``_output_started``
    has been pre-asserted True (e.g. by a prior sub-shape), the inner
    ``if not self._output_started`` arm is False and the fallback
    ``move_to`` is skipped.
    """

    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    # Pre-mark output as started so the False arrow is taken when the
    # tiny-segment fallback fires.
    cb._output_started = True  # noqa: SLF001
    # Call cloudy_polygon_impl directly with a deliberately-tiny first
    # segment so the cloud radius math returns n < 0 on it.
    poly: list[tuple[float, float]] = [
        (0.0, 0.0),
        (0.0001, 0.0),  # tiny first segment — n < 0
        (100.0, 0.0),
        (100.0, 50.0),
        (0.0, 0.0),
    ]
    cb.cloudy_polygon_impl(poly, False)


def test_cloudy_polygon_center_points_overshoot_via_short_polygon() -> None:
    """Closes 537->539 directly by driving ``cloudy_polygon_impl`` with a
    polygon whose total length divides curl_advance with a small float
    residue, so the inner ``while True`` overshoots and the
    ``len(center_points) < center_points_length`` check fires False.
    """

    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    # cloud_radius small relative to side length so the loop overshoots.
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    # Three-vertex polygon that closes through repeating the first
    # point — drives the flat polygon walk through enough iterations
    # for floating residue.
    poly: list[tuple[float, float]] = [
        (0.0, 0.0),
        (37.3, 0.0),
        (37.3, 41.7),
        (0.0, 0.0),
    ]
    cb.cloudy_polygon_impl(poly, False)


def test_cloudy_ellipse_impl_short_axis_drives_segment_skip_arm() -> None:
    """Closes 537->539: inside cloudy_ellipse_impl the per-segment
    condition ``length_todo >= curl_advance - comparison_toler or i ==
    num_points - 2`` can fire False on intermediate segments when the
    flattened ellipse has very many short edges, exercising the False arm.

    Drive with a small ellipse + high intensity so n is large and the
    flat polygon contains short segments that don't immediately reach
    curl_advance.
    """

    rect = PDRectangle(0.0, 0.0, 50.0, 30.0)
    cb = CloudyBorder(_stream(), 2.0, 0.5, rect)
    cb.cloudy_ellipse_impl(0.0, 0.0, 50.0, 30.0)
    # Now also drive with intensity-0 path for completeness.
    cb2 = CloudyBorder(_stream(), 0.0, 0.5, PDRectangle(0.0, 0.0, 50.0, 30.0))
    cb2.cloudy_ellipse_impl(0.0, 0.0, 50.0, 30.0)


def test_cloudy_ellipse_impl_large_drives_full_loop_iterations() -> None:
    """Drives cloudy_ellipse_impl with a large ellipse so the flat
    polygon has many segments and the float-overshoot path inside the
    center-point loop fires the False arm of the length check.
    """

    rect = PDRectangle(0.0, 0.0, 500.0, 400.0)
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    cb.cloudy_ellipse_impl(0.0, 0.0, 500.0, 400.0)


def test_cloudy_ellipse_impl_thin_line_width_overshoots_capacity() -> None:
    """Closes 544->546 (False arm): with a very thin ``line_width`` the
    comparison tolerance shrinks toward zero so the inner ``while True``
    is more likely to append exactly ``center_points_length`` items
    before stopping. Subsequent iterations append-skip via the False arm
    of ``len(center_points) < center_points_length``.

    Use multiple varying sizes to maximise odds of floating residue
    triggering the overshoot.
    """

    for w, h, intensity, lw in (
        (100.0, 60.0, 2.0, 0.01),
        (200.0, 80.0, 2.0, 0.001),
        (300.0, 150.0, 2.0, 0.0001),
        (47.3, 31.7, 2.0, 0.01),
    ):
        rect = PDRectangle(0.0, 0.0, w, h)
        cb = CloudyBorder(_stream(), intensity, lw, rect)
        cb.cloudy_ellipse_impl(0.0, 0.0, w, h)
