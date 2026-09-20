"""PDFBOX-6231 — ``GlyfCompositeDescript.resolve`` aborts on wide nesting.

Upstream (3.0 branch, r1936895) added a guard at the top of the component
loop in ``resolve()``: once the running ``firstIndex`` passes
``Short.MAX_VALUE`` the loop logs an error and breaks, so a maliciously
nested composite glyph cannot keep accumulating point indices.

Upstream shipped no JUnit test with that commit; these are hand-written.
"""

from __future__ import annotations

import logging

from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyf_composite_descript import GlyfCompositeDescript

_LOGGER = "pypdfbox.fontbox.ttf.glyf_composite_descript"


class _FakeDescript:
    """Minimal sub-glyph description: only ``resolve`` / counts are used."""

    def __init__(self, point_count: int, contour_count: int = 1) -> None:
        self._point_count = point_count
        self._contour_count = contour_count

    def resolve(self) -> None:
        return

    def get_point_count(self) -> int:
        return self._point_count

    def get_contour_count(self) -> int:
        return self._contour_count


def _build(component_count: int, points_per_component: int) -> GlyfCompositeDescript:
    """Composite of ``component_count`` components, each pointing at its own
    sub-glyph carrying ``points_per_component`` points."""
    descript = GlyfCompositeDescript()
    components = []
    descriptions = {}
    for index in range(component_count):
        comp = GlyfCompositeComp()
        comp._glyph_index = index  # noqa: SLF001 — bytes-driven ctor bypassed
        components.append(comp)
        descriptions[index] = _FakeDescript(points_per_component)
    descript._components = components  # noqa: SLF001
    descript._descriptions = descriptions  # noqa: SLF001
    return descript


def test_resolve_aborts_once_first_index_passes_short_max_value(caplog) -> None:
    # 10000 points per component: the 5th component is reached with
    # firstIndex == 40000, which is past Short.MAX_VALUE (32767).
    descript = _build(component_count=5, points_per_component=10000)

    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        descript.resolve()

    components = descript.get_components()
    assert [c.get_first_index() for c in components[:4]] == [0, 10000, 20000, 30000]
    # The component that tripped the guard was never assigned — it keeps the
    # constructor default rather than a runaway index.
    assert components[4].get_first_index() == 0
    assert "aborting resolve" in caplog.text
    assert "40000" in caplog.text


def test_resolve_below_the_limit_assigns_every_component(caplog) -> None:
    """Control case: a composite that stays under the ceiling is unaffected."""
    descript = _build(component_count=5, points_per_component=4)

    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        descript.resolve()

    components = descript.get_components()
    assert [c.get_first_index() for c in components] == [0, 4, 8, 12, 16]
    assert [c.get_first_contour() for c in components] == [0, 1, 2, 3, 4]
    assert "aborting resolve" not in caplog.text


def test_resolve_is_still_marked_resolved_after_the_abort() -> None:
    """Upstream breaks out of the loop but still falls through to
    ``resolved = true`` / ``beingResolved = false``, so a second call is a
    no-op rather than a re-walk."""
    descript = _build(component_count=5, points_per_component=10000)
    descript.resolve()

    first_indices = [c.get_first_index() for c in descript.get_components()]
    descript.resolve()
    assert [c.get_first_index() for c in descript.get_components()] == first_indices
