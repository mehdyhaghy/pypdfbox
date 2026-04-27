"""Upstream-test parity placeholder for ``CFFCIDFont``.

Apache PDFBox 3.0.x has **no** dedicated ``CFFCIDFontTest.java`` —
``fontbox/src/test/java/org/apache/fontbox/cff/`` contains
``CFFCharsetTest``, ``CFFEncodingTest``, ``CFFParserTest``,
``CharStringCommandTest``, ``DataInputTest``,
``DataInputRandomAccessTest`` and ``Type1FontUtilTest`` only.
``CFFCIDFont`` is exercised indirectly through ``CFFParserTest``, which
will be ported alongside the parser in a later wave.

We keep the stub file so that:

* the module path ``tests.fontbox.cff.upstream.test_cff_cid_font``
  exists for any cross-references in ``PROVENANCE.md`` to point at;
* future re-syncs against upstream are diffable — if PDFBox ever adds a
  ``CFFCIDFontTest``, dropping the new translation in this same file is
  a clean diff.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="upstream PDFBox 3.0.x has no CFFCIDFontTest.java to port"
)


def test_no_upstream_tests_exist() -> None:
    # Sentinel: kept so pytest collection has at least one item to skip,
    # which keeps the file visible in `pytest --collect-only` output.
    pass
