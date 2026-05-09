from __future__ import annotations

from tests.fontbox.cmap.upstream import test_cmap_parser


def test_identity_hor_bfrange_skipped_body_is_reachable() -> None:
    test_cmap_parser.test_identity_hor_bfrange()
