"""Coverage for the upstream splitter-signature placeholder body."""
from __future__ import annotations

from tests.multipdf.upstream import test_splitter_signatures as signatures_tests


def test_skip_marked_signature_placeholder_body_is_import_callable() -> None:
    test_func = signatures_tests.test_upstream_splitter_signature_test_class_does_not_exist

    test_func()

