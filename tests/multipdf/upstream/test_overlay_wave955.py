from __future__ import annotations

from tests.multipdf.upstream import test_overlay as overlay_mod


def test_wave955_skipped_overlay_placeholders_are_callable_noops() -> None:
    overlay_mod.test_rotated_overlays()
    overlay_mod.test_rotated_overlays_map()
    overlay_mod.test_overlay_on_rotated_source_pages()
