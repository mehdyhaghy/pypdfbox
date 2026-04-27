"""Upstream-test parity placeholder for ``CFFType1Font``.

Apache PDFBox 3.0.x has **no** dedicated ``CFFType1FontTest.java``.
``fontbox/src/test/java/org/apache/fontbox/cff/`` contains
``CFFCharsetTest``, ``CFFEncodingTest``, ``CFFParserTest``,
``CharStringCommandTest``, ``DataInputTest``,
``DataInputRandomAccessTest`` and ``Type1FontUtilTest`` only.
``CFFType1Font`` is exercised indirectly through ``CFFParserTest``,
which will be ported alongside the parser in a later wave.

We keep the stub file so that:

* the module path ``tests.fontbox.cff.upstream.test_cff_type1_font``
  exists for any cross-references in ``PROVENANCE.md`` to point at;
* future re-syncs against upstream are diffable — if PDFBox ever adds a
  ``CFFType1FontTest``, dropping the new translation in this same file
  is a clean diff.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="upstream PDFBox 3.0.x has no CFFType1FontTest.java to port"
)


def test_no_upstream_tests_exist() -> None:
    pass
