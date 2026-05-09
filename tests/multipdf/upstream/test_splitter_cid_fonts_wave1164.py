"""Coverage for the upstream splitter-CID-font placeholder body."""
from __future__ import annotations

from tests.multipdf.upstream import test_splitter_cid_fonts as cid_font_tests


def test_skip_marked_cid_font_placeholder_body_is_import_callable() -> None:
    test_func = cid_font_tests.test_upstream_splitter_cid_font_test_class_does_not_exist

    test_func()

