"""Wave-955 originally guarded the three skipped overlay placeholders
(``test_rotated_overlays`` / ``_map`` / ``_on_rotated_source_pages``) so
nobody could quietly delete them while we waited on the upstream
fixture bundle. Wave 1296 bundled those fixtures and gave each
placeholder a real body — this guard now asserts the migration
landed: the names still exist and now carry real, non-trivial
test code (parametrised, real fixture path imports, the no-input
guard the placeholder always covered).
"""

from __future__ import annotations

import inspect

from tests.multipdf.upstream import test_overlay as overlay_mod


def test_wave955_skipped_overlay_placeholders_are_now_real_tests() -> None:
    # The placeholder names from wave 955 must still resolve so any
    # outside caller importing them keeps working.
    assert callable(overlay_mod.test_rotated_overlays)
    assert callable(overlay_mod.test_rotated_overlays_map)
    assert callable(overlay_mod.test_overlay_on_rotated_source_pages)

    # And they must no longer be empty stubs. The real ports pull in
    # fixtures, so their source is materially larger than the
    # ``def f(): pass`` placeholders wave 955 was guarding.
    for fn in (
        overlay_mod.test_rotated_overlays,
        overlay_mod.test_rotated_overlays_map,
        overlay_mod.test_overlay_on_rotated_source_pages,
    ):
        body = inspect.getsource(fn)
        # An empty `pass` body is two lines tops; real ports are
        # double-digit-line.
        assert body.count("\n") > 5, f"{fn.__name__} is still a stub"
        assert "_FIXTURE_DIR" in body or "OverlayTestBaseRot0" in body, (
            f"{fn.__name__} does not reference the bundled fixtures"
        )
