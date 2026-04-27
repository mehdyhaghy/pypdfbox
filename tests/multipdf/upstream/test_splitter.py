"""Ported placeholder for upstream Splitter tests.

Apache PDFBox 3.0 does not ship a dedicated ``SplitterTest.java``: the
splitter is exercised inside ``PDFMergerUtilityTest.java``. The
``test_split_*`` stubs in :mod:`tests.multipdf.upstream.test_pdf_merger_utility`
are the upstream-named entry points for those tests; each of them is
currently skipped pending the upstream fixture bundle (``PDFA*.pdf``,
``PDFBOX-*.pdf``, structure-tree fixtures) which we don't carry yet.

Hand-written coverage of :class:`pypdfbox.multipdf.Splitter` lives in
:mod:`tests.multipdf.test_splitter` — every API surface upstream exposes
is covered there for the no-fixture case.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Upstream has no SplitterTest.java; coverage lives in test_pdf_merger_utility upstream stubs and tests/multipdf/test_splitter.py")
def test_upstream_splitter_test_class_does_not_exist() -> None:
    pass
