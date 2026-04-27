"""Ported upstream tests for ``SigUtils``.

Upstream ``SigUtils`` lives in ``pdfbox-examples`` (under
``examples/src/main/java/org/apache/pdfbox/examples/signature/SigUtils.java``)
and has no companion JUnit test class — its behavior is covered indirectly
by ``CreateSignatureTest`` / ``ShowSignatureTest`` end-to-end tests that
require live PKCS#7 crypto + signed sample PDFs we don't carry here.

The functional contract of the helpers we ported (``getMDPPermission`` /
``setMDPPermission`` / ``checkCertificateUsage`` /
``checkResponderCertificateUsage`` / ``getLastRelevantSignature``) is fully
covered by the hand-written tests in ``test_sig_utils.py``.
"""

from __future__ import annotations


def test_upstream_has_no_dedicated_sig_utils_test():
    # Marker — see module docstring. Behavior parity is exercised in the
    # hand-written test module rather than via translated JUnit tests.
    assert True
