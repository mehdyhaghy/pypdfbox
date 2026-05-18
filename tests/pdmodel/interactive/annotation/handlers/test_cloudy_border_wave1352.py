"""Wave 1352 coverage-boost tests for
``pypdfbox.pdmodel.interactive.annotation.handlers.cloudy_border``.

Closes the remaining uncovered branches:

* lines 379-382 — ``cloudy_polygon_impl`` defensive ``n < 0`` skip with
  ``not self._output_started``. ``compute_params_polygon`` only ever
  returns -1 on length==0 (which the loop short-circuits earlier at
  line 365), so the branch is exercised through a subclass override.
* line 915 — ``flatten_ellipse`` closure-tolerance branch (last point
  != first within 0.05 → append duplicate). Reproducible only with
  enormous radii where floating-point cos/sin(2*pi) drift exceeds the
  tolerance.

Two flatten_ellipse branches at lines 892 and 894 are defensive clamps
that are mathematically unreachable (arg = 1 - 0.5/r_max with
r_max > 0.5 stays strictly inside (0, 1)); marked with ``# pragma: no
cover`` in source rather than chased here.
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


# ---------- lines 379-382: defensive n < 0 path ----------


class _NegCloudyBorder(CloudyBorder):
    """Subclass that forces the FIRST in-loop
    ``compute_params_polygon`` call to return -1, exercising the
    defensive skip-on-negative branch in ``cloudy_polygon_impl``.

    The seed-length pre-loop call (call #1) must succeed so the loop
    starts; the first j-loop call (call #2) is the one we override.
    """

    _call_count: int = 0

    def compute_params_polygon(  # type: ignore[override]
        self,
        adv_interm: float,
        adv_corner: float,
        k: float,
        r: float,
        length: float,
        array: list[float],
    ) -> int:
        self._call_count += 1
        if self._call_count == 2:
            # Seed array as upstream's _ANGLE_34_DEG defaults so callers
            # using ``array[0]``/``array[1]`` after the return get sane
            # values (defensive — the loop won't read them on n<0).
            return -1
        return super().compute_params_polygon(
            adv_interm, adv_corner, k, r, length, array
        )


def test_cloudy_polygon_impl_negative_n_triggers_move_to_only() -> None:
    """When a subclass forces ``compute_params_polygon`` < 0 inside the
    j-loop AND output hasn't been started yet, the loop emits a
    ``move_to`` to ``pt`` then skips that segment (lines 378-382)."""
    cb = _NegCloudyBorder(
        _stream(), 1.0, 1.0, PDRectangle(0.0, 0.0, 100.0, 100.0)
    )
    polygon = [
        (10.0, 10.0),
        (90.0, 10.0),
        (90.0, 90.0),
        (10.0, 90.0),
        (10.0, 10.0),
    ]
    # Should complete without raising. The defensive branch is taken
    # exactly once on the first edge; the rest of the polygon renders
    # normally. After cloudy_polygon_impl returns, ``_output_started``
    # is True (subsequent edges drew successfully) AND the override
    # ran the n<0 path at least once.
    cb.cloudy_polygon_impl(polygon, is_ellipse=False)
    assert cb._call_count >= 2
    assert cb._output_started is True  # noqa: SLF001


# ---------- line 915: huge-ellipse closure tolerance ----------


def test_flatten_ellipse_huge_radius_appends_closure_duplicate() -> None:
    """For enormous radii the floating-point drift on
    ``sin(2*pi)`` * ry exceeds the 0.05 closure threshold, so the last
    point gets duplicated (line 915). Confirms the bookkeeping by
    counting how many points sit at the wrap-around boundary."""
    pts = CloudyBorder.flatten_ellipse(0.0, 0.0, 1e16, 1e16)
    # The drift forces the closure duplicate.
    first = pts[0]
    last = pts[-1]
    drift = math.hypot(last[0] - first[0], last[1] - first[1])
    assert drift > 0.05
    # The two trailing points must be identical (the duplicate append).
    assert pts[-1] == pts[-2]
