"""Upstream-test parity placeholder for ``Type1CharString``.

Apache PDFBox 3.0.x has **no** ``Type1CharStringTest.java`` —
``fontbox/src/test/java/org/apache/fontbox/cff/`` contains
``CFFCharsetTest``, ``CFFEncodingTest``, ``CFFParserTest``,
``CharStringCommandTest``, ``DataInputTest``,
``DataInputRandomAccessTest`` and ``Type1FontUtilTest`` only. There is
nothing to port.

Re-verified wave 1296 against upstream 3.0 branch HEAD ``e48bce8``:
``find /tmp/pdfbox -name "*Type1CharString*Test*.java"`` still returns
no results.

We keep the stub file so that:

* the module path ``tests.fontbox.cff.upstream.test_type1_char_string``
  exists for any cross-references in PROVENANCE.md to point at;
* future re-syncs against upstream are diffable — if PDFBox ever adds a
  ``Type1CharStringTest``, dropping the new translation in this same
  file is a clean diff.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="upstream PDFBox 3.0.x has no Type1CharStringTest.java to port"
)


def test_no_upstream_tests_exist() -> None:
    # Sentinel: kept so pytest collection has at least one item to skip,
    # which keeps the file visible in `pytest --collect-only` output.
    pass
