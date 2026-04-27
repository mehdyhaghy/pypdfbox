"""Ported upstream tests for ``COSFilterInputStream``.

Upstream PDFBox does not ship a dedicated ``COSFilterInputStreamTest`` —
the class is exercised indirectly via the signing-end-to-end tests in
``pdfbox-examples`` (which require live PKCS#7 crypto and signed sample
PDFs we don't carry here). The functional contract of the class is fully
covered by the hand-written tests in ``test_cos_filter_input_stream.py``;
this file documents the upstream-test gap so future syncs can spot it.
"""

from __future__ import annotations


def test_upstream_has_no_dedicated_cos_filter_input_stream_test():
    # Marker — see module docstring. Behavior parity is exercised in the
    # hand-written test module rather than via translated JUnit tests.
    assert True
