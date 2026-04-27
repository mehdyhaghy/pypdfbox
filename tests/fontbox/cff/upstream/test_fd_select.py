"""Upstream-test parity placeholder for ``FDSelect`` /
``Format0FDSelect`` / ``Format3FDSelect``.

Apache PDFBox 3.0.x has **no** dedicated ``FDSelectTest.java``. The
parser-side ``Format0FDSelect`` / ``Format3FDSelect`` inner classes
are package-private and exercised only indirectly through
``CFFParserTest`` against real CIDKeyed fixtures.

This stub keeps the upstream test path consistent so future re-syncs
against PDFBox are diffable — if upstream ever adds a dedicated
``FDSelectTest``, dropping the translated tests in this file is a
clean diff.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="upstream PDFBox 3.0.x has no FDSelectTest.java to port"
)


def test_no_upstream_tests_exist() -> None:
    pass
