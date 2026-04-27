"""Upstream-test parity placeholder for ``Type2CharString``.

Apache PDFBox 3.0.x has **no** ``Type2CharStringTest.java`` —
``fontbox/src/test/java/org/apache/fontbox/cff/`` contains
``CFFParserTest.java`` and ``CharStringCommandTest.java`` only. There is
nothing to port.

We keep the stub file so that:

* the module path ``tests.fontbox.cff.upstream.test_type2_char_string``
  exists for any cross-references in PROVENANCE.md to point at;
* future re-syncs against upstream are diffable — if PDFBox ever adds a
  ``Type2CharStringTest``, dropping the new translation in this same
  file is a clean diff.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="upstream PDFBox 3.0.x has no Type2CharStringTest.java to port"
)


def test_no_upstream_tests_exist() -> None:
    # Sentinel: kept so pytest collection has at least one item to skip,
    # which keeps the file visible in `pytest --collect-only` output.
    pass
